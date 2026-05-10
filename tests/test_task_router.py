from core.task_router import route_task


def test_messy_filesystem_request_routes_to_filesystem_skill():
    skill = route_task(
        "make a directory under downloades folder called new framea "
        "and copy key farames stored somewhere in folder ranit/frames"
    )
    assert skill.name == "filesystem"
