import re

from src.utils.utils import create_session_id

UUID4_LENGTH = 36
UUID4_FORMAT_REGEX = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$"


def test_create_session_id():
    # when
    session_id = create_session_id()

    # then
    assert len(session_id) == UUID4_LENGTH
    # assert using regex the format of the UUID.
    assert re.match(UUID4_FORMAT_REGEX, session_id) is not None

