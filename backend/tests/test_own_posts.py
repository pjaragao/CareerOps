"""Posts of your own are off (config/automation.yml → linkedin.own_posts): nothing drafted on its own, nothing published."""
import asyncio

import pytest

from app.services.linkedin_api_service import LinkedInApiError
from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot, own_posts_on


def test_own_posts_are_off_in_the_config():
    assert own_posts_on() is False


def test_nothing_is_drafted_or_published_on_its_own():
    assert asyncio.run(Copilot.auto_draft()) is None
    assert Copilot.publish_due() == 0


def test_publishing_by_hand_is_refused_too():
    with pytest.raises(LinkedInApiError, match="desligadas"):
        Copilot.publish_post(1)
