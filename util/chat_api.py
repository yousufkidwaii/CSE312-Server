import json
import uuid
import html
import bcrypt

from util.database import db, chat_collection
from util.response import Response
from util.auth import extract_credentials, validate_password

sessions_collection = db["sessions"]
user_collection = db["users"]
token_collection = db["auth_token"]


def _get_or_create_session(request):
    if "session" in request.cookies:
        session_id = request.cookies["session"].strip()
        doc = sessions_collection.find_one({"_id": session_id})
        if doc and "author" in doc:
            return session_id, doc["author"], False
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

    res = Response().set_status(200, "OK").text("good job gang u sent a chat")
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

    body_obj = json.loads(request.body.decode("utf-8"))
    emoji = body_obj.get("emoji", "")
    if not isinstance(emoji, str) or emoji == "":
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    reactions = doc.get("reactions", {}) or {}
    users = reactions.get(emoji, []) or []

    if session_id in users:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    users.append(session_id)
    reactions[emoji] = users

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

    body_obj = json.loads(request.body.decode("utf-8"))
    emoji = body_obj.get("emoji", "")
    if not isinstance(emoji, str) or emoji == "":
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    reactions = doc.get("reactions", {}) or {}
    users = reactions.get(emoji, []) or []

    if session_id not in users:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    users.remove(session_id)
    if len(users) == 0:
        reactions.pop(emoji, None)
    else:
        reactions[emoji] = users

    chat_collection.update_one({"id": message_id}, {"$set": {"reactions": reactions}})
    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())


def update_nickname(request, handler):
    session_id = _require_session(request)
    if not session_id:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return
    body_obj = json.loads(request.body.decode("utf-8"))
    nickname_raw = body_obj.get("nickname", "")
    if not isinstance(nickname_raw, str):
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    nickname = html.escape(nickname_raw, quote=True).strip()
    if nickname == "":
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    # save nickname on session doc
    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": {"nickname": nickname}},
        upsert=True,
    )
    # retroactively update nickname on old messages
    chat_collection.update_many(
        {"session": session_id},
        {"$set": {"nickname": nickname}},
    )
    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())

'''
==============================================
    HOMEWORK 2 LOs BEING HERE
===============================================
'''

def user_registration(request, handler):
    credentials = extract_credentials(request)
    if credentials is None or len(credentials) < 2:
        res = Response().set_status(400, "Bad Request").text("Bad Request")
        handler.request.sendall(res.to_data())
        return
    username, password = credentials
    if not validate_password(password):
        res = Response().set_status(400, "Bad Request").text("Invalid Password")
        handler.request.sendall(res.to_data())
        return
    if user_collection.find_one({"username": username}):
        res = Response().set_status(400, "Bad Request").text("Username is Taken")
        handler.request.sendall(res.to_data())
        return
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    user_collection.insert_one({
        "user": user_id,
        "username": username,
        "password": hashed_pw
    })

    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())

def user_login(request,handler):
    credentials = extract_credentials(request)
    if credentials is None or len(credentials) < 2:
        res = Response().set_status(400, "Bad Request").text("Invalid Request")
        handler.request.sendall(res.to_data())
        return
    username, password = credentials
    doc = user_collection.find_one({"username": username})
    if not doc:
        res = Response().set_status(400, "Bad Request").text("Invalid username or password")
        handler.request.sendall(res.to_data())
        return
    check_pw = bcrypt.checkpw(password.encode("utf-8"),doc["password"])
    if not check_pw:
        res = Response().set_status(400, "Bad Request").text("Invalid username or password")
        handler.request.sendall(res.to_data())
        return
    auth_token = uuid.uuid4().hex
    hashed_token = bcrypt.hashpw(auth_token.encode("utf-8"), bcrypt.gensalt())

    token_collection.insert_one({
        "id": doc["id"],
        "token": hashed_token
    })
    res = Response().set_status(200, "OK").text("Login successful.")
    res.cookies({
        "auth_token": auth_token,
        "HttpOnly": True,
        "Max-Age": 30*24*60*60
    })
    handler.request.sendall(res.to_data())

#def user_logout(request, handler):

