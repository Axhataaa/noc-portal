from app import app
from models.models import User

with app.app_context():
    user = User.get_by_id(2)
    print("Before:", user.verification_required, user.is_verified)

    User.force_reverify([2])

    user = User.get_by_id(2)
    print("After:", user.verification_required, user.is_verified)