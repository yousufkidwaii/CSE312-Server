from util.chat_api import sessions_collection
from util.response import Response
import uuid
from util.database import db

sessions_collection = db["session"]

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

# This path is provided as an example of how to use the router
def hello_path(request, handler):
    res = Response()
    res.text("hello")
    handler.request.sendall(res.to_data())
