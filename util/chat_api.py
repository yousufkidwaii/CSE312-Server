import json
import uuid
import html

from util.database import db, chat_collection
from util.response import Response

sessions_collection = db["sessions"]


def _get_or_create_session(request):
    if "session" in request.cookies:
        session_id = request.cookies["session"].strip()
        doc = sessions_collection.find_one({"_id": session_id})
        if doc and "author" in doc:
            return session_id, doc["author"], False

        # Cookie exists but missing from DB -> create mapping (no new cookie)
        author = f"user-{uuid.uuid4().hex[:8]}"
        sessions_collection.update_one(
            {"_id": session_id},
            {"$set": {"author": author}},
            upsert=True,
        )
        return session_id, author, False

    session_id = uuid.uuid4().hex
    author = f"user-{uuid.uuid4().hex[:8]}"
    sessions_collection.insert_one({"_id": session_id, "author": author})
    return session_id, author, True


def _require_session(request):
    if "session" not in request.cookies:
        return None
    return request.cookies["session"].strip()


def create_chat(request, handler):
    body_obj = json.loads(request.body.decode("utf-8"))
    content = html.escape(body_obj.get("content", ""), quote=True)

    session_id, author, is_new = _get_or_create_session(request)
    session_doc = sessions_collection.find_one({"_id": session_id}) or {}
    nickname = session_doc.get("nickname")
    msg_id = uuid.uuid4().hex

    chat_collection.insert_one(
        {
            "id": msg_id,
            "author": author,
            "content": content,
            "updated": False,
            "session": session_id,   # ownership check
            "deleted": False, # soft delete
            "reactions": {},
            "nickname": nickname if isinstance(nickname, str) else None,
        }
    )

    # Spec says response must be EXACTLY this string
    res = Response().set_status(200, "O").text("good job gang u sent a chat")
    if is_new:
        res.cookies({"session": session_id})
    handler.request.sendall(res.to_data())


def get_chats(request, handler):
    docs = chat_collection.find({"deleted": {"$ne": True}}).sort("_id", 1)

    messages = []
    for d in docs:
        msg = {
                "author": d.get("author", ""),
                "id": d.get("id", ""),
                "content": d.get("content", ""),
                "updated": bool(d.get("updated", False)),
                "reactions": d.get("reactions", {}) or {},
            }
        if "nickname" in d and isinstance(d.get("nickname"), str):
            msg["nickname"] = d.get("nickname")
        messages.append(msg)

    res = Response().json({"messages": messages})
    handler.request.sendall(res.to_data())


def update_chat(request, handler):
    session_id = _require_session(request)
    if not session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    msg_id = request.path.split("/api/chats/", 1)[1]
    doc = chat_collection.find_one({"id": msg_id, "deleted": {"$ne": True}})
    if not doc:
        res = Response().set_status(404, "Not Found").text("Not Found")
        handler.request.sendall(res.to_data())
        return

    if doc.get("session") != session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    body_obj = json.loads(request.body.decode("utf-8"))
    content = html.escape(body_obj.get("content", ""), quote=True)

    chat_collection.update_one({"id": msg_id}, {"$set": {"content": content, "updated": True}})
    res = Response().set_status(200, "OK").text("updated")
    handler.request.sendall(res.to_data())


def delete_chat(request, handler):
    session_id = _require_session(request)
    if not session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    msg_id = request.path.split("/api/chats/", 1)[1]
    doc = chat_collection.find_one({"id": msg_id, "deleted": {"$ne": True}})
    if not doc:
        res = Response().set_status(404, "Not Found").text("Not Found")
        handler.request.sendall(res.to_data())
        return

    if doc.get("session") != session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    chat_collection.update_one({"id": msg_id}, {"$set": {"deleted": True}})
    res = Response().set_status(200, "OK").text("deleted")
    handler.request.sendall(res.to_data())


def add_reaction(request, handler):
    session_id = _require_session(request)
    if not session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    message_id = request.path.split("/api/reaction/", 1)[1]
    doc = chat_collection.find_one({"id": message_id, "deleted": {"$ne": True}})
    if not doc:
        res = Response().set_status(404, "Not Found").text("Not Found")
        handler.request.sendall(res.to_data())
        return

    try:
        body_obj = json.loads(request.body.decode("utf-8"))
    except Exception:
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    emoji = body_obj.get("emoji", "")
    if not isinstance(emoji, str) or emoji == "":
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    reactions = doc.get("reactions", {}) or {}
    users_for_emoji = reactions.get(emoji, []) or []

    if session_id in users_for_emoji:
        # same user trying to react with same emoji again
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    users_for_emoji.append(session_id)
    reactions[emoji] = users_for_emoji

    chat_collection.update_one({"id": message_id}, {"$set": {"reactions": reactions}})
    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())


def remove_reaction(request, handler):
    session_id = _require_session(request)
    if not session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    message_id = request.path.split("/api/reaction/", 1)[1]
    doc = chat_collection.find_one({"id": message_id, "deleted": {"$ne": True}})
    if not doc:
        res = Response().set_status(404, "Not Found").text("Not Found")
        handler.request.sendall(res.to_data())
        return

    try:
        body_obj = json.loads(request.body.decode("utf-8"))
    except Exception:
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    emoji = body_obj.get("emoji", "")
    if not isinstance(emoji, str) or emoji == "":
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    reactions = doc.get("reactions", {})
    users_for_emoji = reactions.get(emoji, [])

    if session_id not in users_for_emoji:
        # user tried to remove a reaction they don't have
        res = Response().set_status(403, "Forbidden").text("Can't remove another person's reaction")
        handler.request.sendall(res.to_data())
        return

    users_for_emoji.remove(session_id)

    if len(users_for_emoji) == 0:
        reactions.pop(emoji, None)
    else:
        reactions[emoji] = users_for_emoji

    chat_collection.update_one({"id": message_id}, {"$set": {"reactions": reactions}})
    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())

def add_nickname(request, handler):
    session_id = _require_session(request)
    if not session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return
    try:
        body_obj = json.loads(request.body.decode("utf-8"))
    except Exception:
        res = Response().set_status(403,"Forbidden").text("Forbidden")
        handler.request.send(res.to_data())
        return
    nickname = body_obj.get("nickname", "")
    if not isinstance(nickname. str):
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.send(res.to_data())
        return
    change_nickname = html.escape(nickname, quote=True)
    sessions_collection.update_one(
        {"id": session_id},
        {"$set": {"nickname": change_nickname, "author": change_nickname}},
        upsert=True,
    )
    chat_collection.update_many(
        {"session": session_id},
        {"$set": {"author": change_nickname, "nickname": change_nickname}},
    )
    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())
