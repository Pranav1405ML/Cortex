from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message

# When Alembic scans for models to generate migrations, it needs all
# model classes to be imported somewhere. This __init__.py does that.
# It's also convenient for imports: `from app.models import User`

__all__ = ["User", "Conversation", "Message"]
