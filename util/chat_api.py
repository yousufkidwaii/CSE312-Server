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
    msg_id = uuid.uuid4().hex

    chat_collection.insert_one(
        {
            "id": msg_id,
            "author": author,
            "content": content,
            "updated": False,
            "session": session_id,   # ownership check
            "deleted": False,        # soft delete
        }
    )

    # Spec says response must be EXACTLY this string
    res = Response().set_status(200, "OK").text("Great work sending a chat message!!")
    if is_new:
        res.cookies({"session": session_id})
    handler.request.sendall(res.to_data())


def get_chats(request, handler):
    docs = chat_collection.find({"deleted": {"$ne": True}}).sort("_id", 1)

    messages = []
    for d in docs:
        messages.append(
            {
                "author": d.get("author", ""),
                "id": d.get("id", ""),
                "content": d.get("content", ""),
                "updated": bool(d.get("updated", False)),
            }
        )

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
