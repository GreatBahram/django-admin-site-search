"""Verify that overrideable functions, in the view, are invoked correctly"""
from functools import partial
from typing import Optional
from unittest.mock import MagicMock, patch

import django
import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client

from dev.football.stadiums.models import Stadium
from dev.football.teams.models import Team
from tests import request_search


def _request_with_patch(
    client: Client,
    user: User,
    method_name: str,
    site_search_method: Optional[str] = None,
) -> MagicMock:
    """Requests a search, with the given method patched. The user is set up with "view" access
    to the Team and Stadium models"""
    permission_ids = Permission.objects.filter(
        codename__in=["view_team", "view_stadium"]
    ).values_list("id", flat=True)
    user.user_permissions.add(*permission_ids)

    # return_value=None works for now, but consider a relevant value per-method
    with patch(
        f"dev.admin.CustomAdminSite.{method_name}", return_value=None
    ) as patch_method:
        request_search(client, query="QuEry", site_search_method=site_search_method)

    return patch_method


@pytest.fixture()
def request_with_patch(client_admin, user_admin):
    """Applies the admin client/user fixtures to the _request_with_patch helper"""
    return partial(_request_with_patch, client_admin, user_admin)


def test_match_apps(request_with_patch):
    """Verify the match_app method is correctly invoked for each app that the user has access to"""
    patch_match_app = request_with_patch(method_name="match_app")
    call_args_list = [c[0] for c in patch_match_app.call_args_list]

    assert len(call_args_list) == 2
    assert ("QuEry", "Stadiums") in call_args_list
    assert ("QuEry", "Teams") in call_args_list


def test_match_model(request_with_patch):
    """Verify the match_model method is correctly invoked for each model that the user has access to"""
    patch_match_model = request_with_patch(method_name="match_model")
    call_args_list = [c[0] for c in patch_match_model.call_args_list]

    assert len(call_args_list) == 2
    assert (
        "QuEry",
        "Stadiums",
        "Stadium",
        Stadium._meta.get_fields(),
    ) in call_args_list
    assert ("QuEry", "Teams", "Team", Team._meta.get_fields()) in call_args_list


@pytest.mark.parametrize(
    "site_search_method", ["model_char_fields", "admin_search_fields"]
)
def test_match_objects(request_with_patch, site_search_method):
    """Verify the match_objects method is correctly invoked for each model that the user has access to"""
    patch_match_objects = request_with_patch(
        method_name="match_objects", site_search_method=site_search_method
    )
    call_args_list = [c[0] for c in patch_match_objects.call_args_list]

    assert len(call_args_list) == 2
    assert ("QuEry", Stadium, Stadium._meta.get_fields()) in call_args_list
    assert ("QuEry", Team, Team._meta.get_fields()) in call_args_list


def test_filter_field_invoked(request_with_patch):
    """Verify the filter_field method is correctly invoked for each field, on each model, that the user
    has access to.... only if site_search_method is model_char_fields"""
    patch_field_fields = request_with_patch(
        method_name="filter_field", site_search_method="model_char_fields"
    )
    call_args_list = [c[0] for c in patch_field_fields.call_args_list]
    expected_fields = Stadium._meta.get_fields() + Team._meta.get_fields()

    assert len(call_args_list) == len(expected_fields)
    for field in expected_fields:
        # query should be passed in as-is (regression: was previously passed in as .lower())
        assert ("QuEry", field) in call_args_list


def test_filter_field_not_invoked(request_with_patch):
    """Verify the filter_field method is not invoked if site_search_method is admin_search_fields"""
    patch_field_fields = request_with_patch(
        method_name="filter_field", site_search_method="admin_search_fields"
    )

    assert patch_field_fields.call_count == 0


def test_get_model_class(request_with_patch):
    """Verify that the get_model_class method is correctly invoked for each model that the
    user has access to"""
    patch_get_model_class = request_with_patch(method_name="get_model_class")
    call_args_list = [c[0] for c in patch_get_model_class.call_args_list]

    stadium_dict = {
        "name": "Stadiums",
        "object_name": "Stadium",
        "perms": {"add": False, "change": False, "delete": False, "view": True},
        "admin_url": "/admin/stadiums/stadium/",
        "add_url": None,
        "view_only": True,
    }

    team_dict = {
        "name": "Teams",
        "object_name": "Team",
        "perms": {"add": False, "change": False, "delete": False, "view": True},
        "admin_url": "/admin/teams/team/",
        "add_url": None,
        "view_only": True,
    }

    if django.VERSION[0] >= 4:
        # model class only available in version >= 4.0.0
        stadium_dict["model"] = Stadium
        team_dict["model"] = Team

    assert len(call_args_list) == 2
    assert ("stadiums", stadium_dict) in call_args_list
    assert ("teams", team_dict) in call_args_list
