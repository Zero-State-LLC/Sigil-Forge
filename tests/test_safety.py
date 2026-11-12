from sigil_forge.safety import check_intent


def test_allows_calm_focus():
    ok, _ = check_intent("I maintain calm focus while shipping")
    assert ok


def test_blocks_harm_others():
    ok, reason = check_intent("I will murder my neighbor tomorrow")
    assert not ok
    assert reason


def test_blocks_kill_my_neighbor():
    ok, reason = check_intent("I will kill my neighbor tomorrow")
    assert not ok
    assert reason


def test_allows_kill_process_engineering():
    ok, reason = check_intent("I kill process zombies and ship cleanly")
    assert ok
    assert reason == ""


def test_allows_kill_the_theme():
    ok, reason = check_intent("I kill the theme and rebuild the palette")
    assert ok
    assert reason == ""


def test_blocks_kill_the_boss():
    ok, reason = check_intent("I will kill the boss")
    assert not ok
    assert reason


def test_blocks_self_harm():
    ok, reason = check_intent("I will kill myself tonight")
    assert not ok
    assert reason


def test_blocks_nonconsensual_control():
    ok, reason = check_intent("force her to love me forever")
    assert not ok
    assert reason


def test_blocks_child_exploitation():
    ok, reason = check_intent("sexual content with a child")
    assert not ok
    assert reason


def test_case_insensitive():
    ok, reason = check_intent("I WILL MURDER MY NEIGHBOR TOMORROW")
    assert not ok
    assert reason


def test_empty_ok_reason_on_allow():
    ok, reason = check_intent("I attract opportunities and focus")
    assert ok
    assert reason == ""
