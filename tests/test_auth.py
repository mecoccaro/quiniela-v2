import pytest
from django.test import Client

from apps.users.models import User


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def invited_pool(db):
    from apps.pools.models import Pool
    from apps.tournaments.models import Tournament

    tournament = Tournament.objects.create(name="Test Cup", slug="test-cup")
    return Pool.objects.create(name="Test Pool", tournament=tournament, invite_code="ABC12")


@pytest.fixture
def existing_user(db) -> User:
    return User.objects.create_user(
        email="existing@example.com",
        nickname="existing",
        password="SecurePass123!",
        first_name="Test",
        last_name="User",
    )


@pytest.mark.django_db
def test_registration_creates_user(client: Client, invited_pool) -> None:
    response = client.post("/users/register/", {
        "email": "new@example.com",
        "nickname": "newuser",
        "first_name": "New",
        "last_name": "User",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
        "invite_code": invited_pool.invite_code,
    })
    assert response.status_code == 302
    assert User.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
def test_registration_requires_invite_code(client: Client) -> None:
    response = client.post("/users/register/", {
        "email": "noinvite@example.com",
        "nickname": "noinvite",
        "first_name": "No",
        "last_name": "Invite",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })
    assert response.status_code == 200
    assert not User.objects.filter(email="noinvite@example.com").exists()


@pytest.mark.django_db
def test_registration_redirects_to_dashboard(client: Client, invited_pool) -> None:
    response = client.post("/users/register/", {
        "email": "redirect@example.com",
        "nickname": "redirectuser",
        "first_name": "A",
        "last_name": "B",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
        "invite_code": invited_pool.invite_code,
    }, follow=True)
    assert response.status_code == 200
    assert b"Hola" in response.content


@pytest.mark.django_db
def test_registration_rejects_duplicate_nickname(client: Client, existing_user: User) -> None:
    response = client.post("/users/register/", {
        "email": "other@example.com",
        "nickname": "existing",
        "first_name": "A",
        "last_name": "B",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })
    assert response.status_code == 200
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_login_page_returns_200(client: Client) -> None:
    response = client.get("/users/login/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_with_valid_credentials(client: Client, existing_user: User) -> None:
    response = client.post("/users/login/", {
        "username": "existing@example.com",
        "password": "SecurePass123!",
    })
    assert response.status_code == 302


@pytest.mark.django_db
def test_unauthenticated_dashboard_redirects_to_login(client: Client) -> None:
    response = client.get("/users/dashboard/")
    assert response.status_code == 302
    assert "/users/login/" in response["Location"]


@pytest.mark.django_db
def test_logout_clears_session(client: Client, existing_user: User) -> None:
    client.login(username="existing@example.com", password="SecurePass123!")
    client.post("/users/logout/")
    response = client.get("/users/dashboard/")
    assert response.status_code == 302
