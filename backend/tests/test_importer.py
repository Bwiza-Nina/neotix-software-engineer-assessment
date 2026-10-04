from app.services.importer import parse_csv


def test_parse_skips_known_messy_rows():
    csv_text = """episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality
EP-00001,arm-01,pick cup,2026-08-30T10:25:00,102,Diane,good
EP-00001,arm-01,pick cup,2026-08-30T10:25:00,102,Diane,good
,humanoid-01,fold towel,2026-08-13T06:59:00,82,Patrick,good
EP-00020,mobile-01,fold towel,2026-08-11T00:14:00,90,Patrick,excellent
EP-00017,humanoid-01,place cup on shelf,2026-09-12T10:46:00,-5,Diane,good
EP-00023,arm-02,pour water,not a date,71,Aline,good
EP-00024,arm-99,place cup on shelf,2026-09-09T12:33:00,88,Eric,usable
EP-00016,arm-02,place cup on shelf,2026-09-03T12:24:00,,Patrick,good
EP-00019,arm-02,pour water,2026-08-04T08:17:00,120,Kevin,
EP-00025,arm-01,fold towel,2031-01-01T00:00:00,56,Jeanne,usable
EP-90001,arm-02,open drawer,2026-08-20T10:00:00,30
EP-90003,arm-01,fold towel,2026-08-22T09:00:00,N/A,Aline,good
EP-90004,arm-01,fold towel,2026-08-22T09:05:00,999999,Aline,good
ep-00003,arm-02,wipe table,2026-08-22T09:10:00,33,Eric,good
EP-00006,arm-01,  Pick Cup ,2026-08-13T23:51:00,111,Eric,usable
EP-00007,arm-03,PICK CUP,2026-08-16T19:38:00,35,Diane,good
EP-00008, arm-01,pick cup,2026-08-05T13:18:00,53,Diane,bad
EP-00014,arm-03,open drawer,14/08/2026 09:15,34,Kevin,good
EP-00013,arm-01,fold towel,2026-08-14 09:12:00,43,Patrick,good
EP-00009,arm-01,stack blocks,2026-08-13T08:55:00,66,Jeanne,Good
EP-00018,arm-01,wipe table,2026-08-11T18:10:00,45.5,Patrick,good
EP-00010,mobile-01,pick cup,2026-09-14T14:54:00,78,Diane,USABLE
EP-00021,,place cup on shelf,2026-08-13T09:19:00,103,Jeanne,usable
"""
    accepted, skipped = parse_csv(csv_text)
    reasons = {s.reason.split(":")[0] if False else s.reason for s in skipped}
    ids = {e.episode_id for e in accepted}

    assert "EP-00001" in ids
    assert any("duplicate" in s.reason for s in skipped)
    assert any("missing episode_id" in s.reason for s in skipped)
    assert any("invalid quality" in s.reason for s in skipped)
    assert any("invalid duration" in s.reason for s in skipped)
    assert any("unparseable recorded_at" in s.reason for s in skipped)
    assert any("unknown robot_id" in s.reason for s in skipped)
    assert any("missing duration" in s.reason for s in skipped)
    assert any("missing quality" in s.reason for s in skipped)
    assert any("future" in s.reason for s in skipped)
    assert any("malformed" in s.reason for s in skipped)
    assert any("missing robot_id" in s.reason for s in skipped)

    pick = next(e for e in accepted if e.episode_id == "EP-00006")
    assert pick.task_name == "pick cup"
    good_case = next(e for e in accepted if e.episode_id == "EP-00009")
    assert good_case.quality == "good"
    usable_case = next(e for e in accepted if e.episode_id == "EP-00010")
    assert usable_case.quality == "usable"
    padded_robot = next(e for e in accepted if e.episode_id == "EP-00008")
    assert padded_robot.robot_id == "arm-01"
    float_dur = next(e for e in accepted if e.episode_id == "EP-00018")
    assert float_dur.duration_seconds == 46
    assert "EP-00003" in ids
    assert reasons  # skipped set is non-empty
