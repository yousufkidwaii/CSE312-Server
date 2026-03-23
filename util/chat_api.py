import json
import uuid
import html
import bcrypt
import hashlib

from pathlib import Path
from datetime import datetime

from util.database import db, chat_collection
from util.response import Response
from util.request import Request
from util.auth import extract_credentials, validate_password
from util.multipart import parse_multipart

sessions_collection = db["sessions"]
user_collection = db["users"]
video_collection = db["videos"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"
AVATAR_DIR = PUBLIC_DIR / "imgs" / "avatars"
VIDEO_DIR = PUBLIC_DIR / "videos"


def _ensure_upload_dirs():
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def _default_image_url():
    return "/public/imgs/user.webp"


def _get_authenticated_user(request):
    token = request.cookies.get("auth_token")
    if not token:
        return None
    hashed_token = hashlib.sha256(token.encode("utf-8")).digest()
    return user_collection.find_one({"auth_token": hashed_token})


def _extract_filename(part):
    content_disposition = part.headers.get("Content-Disposition", "")
    pieces = content_disposition.split(";")
    for piece in pieces:
        piece = piece.strip()
        if piece.startswith("filename="):
            return piece[len("filename="):].strip().strip('"')
    return ""


def _get_extension(filename):
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[1].lower()


def _get_or_create_session(request):
    if "session" in request.cookies:
        session_id = request.cookies["session"].strip()
        doc = sessions_collection.find_one({"_id": session_id})

        author = None
        if doc and "author" in doc:
            author = doc["author"]

        token = request.cookies.get("auth_token")
        if token:
            hashed_token = hashlib.sha256(token.encode("utf-8")).digest()
            user_doc = user_collection.find_one({"auth_token": hashed_token})
            if user_doc:
                author = user_doc["username"]

        if not author:
            author = f"guest-{uuid.uuid4().hex[:8]}"

        sessions_collection.update_one(
            {"_id": session_id},
            {"$set": {"author": author}},
            upsert=True,
        )
        return session_id, author, False

    session_id = uuid.uuid4().hex
    author = None

    token = request.cookies.get("auth_token")
    if token:
        hashed_token = hashlib.sha256(token.encode("utf-8")).digest()
        user_doc = user_collection.find_one({"auth_token": hashed_token})
        if user_doc:
            author = user_doc["username"]

    if not author:
        author = f"guest-{uuid.uuid4().hex[:8]}"

    sessions_collection.insert_one({"_id": session_id, "author": author})
    return session_id, author, True


def _require_session(request):
    if "session" not in request.cookies:
        return None
    return request.cookies["session"].strip()


def require_auth(request):
    if "auth_token" not in request.cookies:
        return None
    return request.cookies["auth_token"].strip()


def create_chat(request, handler):
    body_obj = json.loads(request.body.decode("utf-8"))
    content = html.escape(body_obj.get("content", ""), quote=True)

    session_id, author, is_new = _get_or_create_session(request)
    session_doc = sessions_collection.find_one({"_id": session_id}) or {}
    nickname = session_doc.get("nickname")

    user_doc = _get_authenticated_user(request)
    image_url = _default_image_url()
    if user_doc and user_doc.get("imageURL"):
        image_url = user_doc["imageURL"]

    msg_id = uuid.uuid4().hex
    chat_collection.insert_one(
        {
            "id": msg_id,
            "author": author,
            "content": content,
            "updated": False,
            "session": session_id,
            "deleted": False,
            "reactions": {},
            "nickname": nickname if isinstance(nickname, str) else None,
            "imageURL": image_url,
        }
    )

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
            "imageURL": d.get("imageURL", _default_image_url()),
        }
        if "nickname" in d and isinstance(d.get("nickname"), str):
            msg["nickname"] = d.get("nickname")
        messages.append(msg)

    res = Response().json({"messages": messages})
    handler.request.sendall(res.to_data())


def update_chat(request, handler):
    session_id, author, isnew = _get_or_create_session(request)
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

    if doc.get("author") != author:
        res = Response().set_status(403, "Forbidden").text("Forbidden")
        handler.request.sendall(res.to_data())
        return

    body_obj = json.loads(request.body.decode("utf-8"))
    content = html.escape(body_obj.get("content", ""), quote=True)

    chat_collection.update_one(
        {"id": msg_id},
        {"$set": {"content": content, "updated": True}}
    )

    res = Response().set_status(200, "OK").text("updated")
    handler.request.sendall(res.to_data())


def delete_chat(request, handler):
    session_id, author, _ = _get_or_create_session(request)
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

    if doc.get("author") != author:
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

    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": {"nickname": nickname}},
        upsert=True,
    )

    chat_collection.update_many(
        {"session": session_id},
        {"$set": {"nickname": nickname}},
    )

    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())


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

    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    user_collection.insert_one({
        "username": username,
        "password": hashed_pw
    })

    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())


def user_login(request, handler):
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

    check_pw = bcrypt.checkpw(password.encode("utf-8"), doc["password"])
    if not check_pw:
        res = Response().set_status(400, "Bad Request").text("Invalid username or password")
        handler.request.sendall(res.to_data())
        return

    auth_token = uuid.uuid4().hex
    hashed_token = hashlib.sha256(auth_token.encode("utf-8")).digest()

    session_id = _require_session(request)
    if session_id:
        sessions_collection.update_one(
            {"_id": session_id},
            {"$set": {"author": username}},
            upsert=True,
        )

    user_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"auth_token": hashed_token}}
    )

    res = Response().set_status(200, "OK").text("Login successful.")
    res.cookies({
        "auth_token": auth_token,
        "HttpOnly": True,
        "Max-Age": 30 * 24 * 60 * 60,
    })
    handler.request.sendall(res.to_data())


def user_logout(request, handler):
    token = request.cookies.get("auth_token")
    if token:
        hashed_token = hashlib.sha256(token.encode("utf-8")).digest()
        user_collection.update_one(
            {"auth_token": hashed_token},
            {"$set": {"auth_token": None}}
        )

    res = Response().set_status(302, "Found").text("Logout successful")
    res.headers({"Location": "/"})
    res.cookies({
        "auth_token": "",
        "HttpOnly": True,
        "Max-Age": 0,
    })
    handler.request.sendall(res.to_data())


def get_me(request, handler):
    token = request.cookies.get("auth_token")
    if not token:
        res = Response().set_status(401, "Unauthorized").json({})
        handler.request.sendall(res.to_data())
        return

    hashed_token = hashlib.sha256(token.encode("utf-8")).digest()
    user = user_collection.find_one({"auth_token": hashed_token})
    if not user:
        res = Response().set_status(401, "Unauthorized").json({})
        handler.request.sendall(res.to_data())
        return

    data = {
        "username": user["username"],
        "id": str(user["_id"]),
        "imageURL": user.get("imageURL", _default_image_url())
    }

    res = Response().set_status(200, "OK").json(data)
    handler.request.sendall(res.to_data())


def upload_avatar(request, handler):
    user_doc = _get_authenticated_user(request)
    if not user_doc:
        res = Response().set_status(401, "Unauthorized").text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    _ensure_upload_dirs()
    multipart_data = parse_multipart(request)

    avatar_part = None
    for part in multipart_data.parts:
        if part.name == "avatar":
            avatar_part = part
            break

    if avatar_part is None:
        res = Response().set_status(400, "Bad Request").text("Missing avatar")
        handler.request.sendall(res.to_data())
        return

    filename = _extract_filename(avatar_part)
    ext = _get_extension(filename)

    if ext not in [".jpg", ".jpeg", ".png", ".gif"]:
        res = Response().set_status(400, "Bad Request").text("Invalid image type")
        handler.request.sendall(res.to_data())
        return

    old_image_url = user_doc.get("imageURL")
    new_filename = str(user_doc["_id"]) + ext
    file_path = AVATAR_DIR / new_filename

    with open(file_path, "wb") as f:
        f.write(avatar_part.content)

    new_image_url = "/public/imgs/avatars/" + new_filename

    user_collection.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"imageURL": new_image_url}}
    )

    if old_image_url and old_image_url.startswith("/public/imgs/avatars/") and old_image_url != new_image_url:
        old_file = PUBLIC_DIR / old_image_url[len("/public/"):]
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                pass

    res = Response().set_status(200, "OK").text("Avatar uploaded successfully")
    handler.request.sendall(res.to_data())


def search_users(request, handler):
    query = request.path.split("?")
    id, sep, search = query[1].partition("=")

    if search == "":
        res = Response().set_status(200, "OK").json({"users": []})
        handler.request.sendall(res.to_data())
        return

    cursor = user_collection.find({"username": {"$regex": f"^{search}"}})
    collection = []
    for user in cursor:
        collection.append({"id": str(user["_id"]), "username": user["username"]})

    res = Response().set_status(200, "OK").json({"users": collection})
    handler.request.sendall(res.to_data())


def update_users(request, handler):
    credentials = extract_credentials(request)
    if credentials is None or len(credentials) < 1:
        res = Response().set_status(400, "Bad Request").text("Please enter credentials")
        handler.request.sendall(res.to_data())
        return

    username = credentials[0]
    password = credentials[1] if len(credentials) > 1 else ""

    token = request.cookies.get("auth_token")
    if not token:
        res = Response().set_status(401, "Unauthorized").text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    hashed_token = hashlib.sha256(token.encode("utf-8")).digest()
    user_doc = user_collection.find_one({"auth_token": hashed_token})
    if not user_doc:
        res = Response().set_status(401, "Unauthorized").text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    if password != "" and not validate_password(password):
        res = Response().set_status(400, "Bad Request").text("Invalid password")
        handler.request.sendall(res.to_data())
        return

    if username != user_doc["username"] and user_collection.find_one({"username": username}):
        res = Response().set_status(400, "Bad Request").text("Username is taken")
        handler.request.sendall(res.to_data())
        return

    update_fields = {"username": username}
    if password != "":
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        update_fields["password"] = hashed_pw

    user_collection.update_one(
        {"_id": user_doc["_id"]},
        {"$set": update_fields}
    )

    res = Response().set_status(200, "OK").text("OK")
    handler.request.sendall(res.to_data())


def upload_video(request, handler):
    user_doc = _get_authenticated_user(request)
    if not user_doc:
        res = Response().set_status(401, "Unauthorized").text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    _ensure_upload_dirs()
    multipart_data = parse_multipart(request)

    title_part = None
    description_part = None
    video_part = None

    for part in multipart_data.parts:
        if part.name == "title":
            title_part = part
        elif part.name == "description":
            description_part = part
        elif part.name == "video":
            video_part = part

    if title_part is None or description_part is None or video_part is None:
        res = Response().set_status(400, "Bad Request").text("Missing upload fields")
        handler.request.sendall(res.to_data())
        return

    filename = _extract_filename(video_part)
    ext = _get_extension(filename)
    if ext != ".mp4":
        res = Response().set_status(400, "Bad Request").text("Only mp4 is allowed")
        handler.request.sendall(res.to_data())
        return

    try:
        title = html.escape(title_part.content.decode("utf-8"), quote=True)
        description = html.escape(description_part.content.decode("utf-8"), quote=True)
    except UnicodeDecodeError:
        res = Response().set_status(400, "Bad Request").text("Invalid text fields")
        handler.request.sendall(res.to_data())
        return

    video_id = uuid.uuid4().hex
    video_filename = video_id + ".mp4"
    file_path = VIDEO_DIR / video_filename

    with open(file_path, "wb") as f:
        f.write(video_part.content)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    video_path = "/public/videos/" + video_filename

    video_collection.insert_one(
        {
            "id": video_id,
            "author_id": str(user_doc["_id"]),
            "author_username": user_doc["username"],
            "title": title,
            "description": description,
            "video_path": video_path,
            "created_at": created_at,
            "uploader_imageURL": user_doc.get("imageURL", _default_image_url()),
            "thumbnailURL": "/public/imgs/user.webp",
        }
    )

    res = Response().set_status(200, "OK").json({"id": video_id})
    handler.request.sendall(res.to_data())


def get_videos(request, handler):
    docs = video_collection.find().sort("_id", -1)
    videos = []

    for doc in docs:
        videos.append(
            {
                "author_id": doc.get("author_id", ""),
                "title": doc.get("title", ""),
                "description": doc.get("description", ""),
                "video_path": doc.get("video_path", ""),
                "created_at": doc.get("created_at", ""),
                "id": doc.get("id", ""),
                "thumbnailURL": doc.get("thumbnailURL", "/public/imgs/user.webp"),
            }
        )

    res = Response().set_status(200, "OK").json({"videos": videos})
    handler.request.sendall(res.to_data())


def get_single_video(request, handler):
    video_id = request.path.split("/api/videos/", 1)[1]
    doc = video_collection.find_one({"id": video_id})

    if not doc:
        res = Response().set_status(404, "Not Found").text("Not Found")
        handler.request.sendall(res.to_data())
        return

    video = {
        "author_id": doc.get("author_id", ""),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "video_path": doc.get("video_path", ""),
        "created_at": doc.get("created_at", ""),
        "id": doc.get("id", ""),
        "imageURL": doc.get("uploader_imageURL", _default_image_url()),
        "author_username": doc.get("author_username", "Video Uploader"),
    }

    res = Response().set_status(200, "OK").json({"video": video})
    handler.request.sendall(res.to_data())