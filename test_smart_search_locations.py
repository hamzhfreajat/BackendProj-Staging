"""
Regression tests for the smart search location resolver.
Run with:  python test_smart_search_locations.py   (or pytest)

Every bug reported against smart search locations gets a case here.
"""
from smart_search_locations import resolve_locations, match_city

AMMAN, IRBID, AQABA, ZARQA = 1, 2, 3, 4
CITIES = [(AMMAN, "عمان"), (IRBID, "اربد"), (AQABA, "العقبة"), (ZARQA, "الزرقاء")]

REGIONS = [
    # (id, city_id, name_ar)
    (10, AMMAN, "الزهور"),
    (11, AMMAN, "خلدا"),
    (12, AMMAN, "الوحدات"),
    (13, AMMAN, "وسط البلد"),
    (14, AMMAN, "الدوار السابع"),
    (15, AMMAN, "شارع الجامعة (الجامعة الأردنية)"),
    (16, AMMAN, "الحي الشرقي"),
    (20, IRBID, "الزهور"),
    (21, IRBID, "الحي الشرقي"),
    (22, IRBID, "البلد"),
    (23, IRBID, "حي التركمان"),
    (30, AQABA, "الوحدات الشرقية"),
    (31, AQABA, "البلد القديمة"),
    (32, AQABA, "السكنية 8 (الثامنة)"),
    (33, AQABA, "السكنية 3 (الثالثة)"),
    (40, ZARQA, "الزرقاء الجديدة"),
]

ALIASES = [
    # (alias_name, region_id)
    ("الاذاعة", 11),
    ("البلد", 31),
]


def resolve(**kwargs):
    return resolve_locations(CITIES, REGIONS, ALIASES, **kwargs)


def test_stated_city_blocks_same_name_in_other_city():
    # "في شارع الأدعية أو الزهور بدي بس بعمان" must never return Irbid's الزهور
    r = resolve(city_names=["عمان"], region_names=["شارع الأدعية", "الزهور"])
    assert r.city_id == AMMAN
    assert r.region_ids == [10]
    assert r.not_found == ["شارع الأدعية"]
    assert not r.ambiguous


def test_city_with_preposition_inside_regions():
    # The AI sometimes leaves the city in the regions list, with its prefix
    r = resolve(region_names=["الزهور", "بعمان"])
    assert r.city_id == AMMAN
    assert r.region_ids == [10]


def test_aqaba_query_never_resolves_to_amman_or_irbid():
    # "الوحدات الشرقية / البلد / قرب دوار هيا العقبة"
    r = resolve(
        city_names=["العقبة"],
        region_names=["الوحدات الشرقية", "البلد"],
        landmarks=[{"name": "دوار هيا", "region": "السكنية الثامنة", "city": "العقبة"}],
    )
    assert r.city_id == AQABA
    assert set(r.region_ids) == {30, 31, 32}
    assert all(region_id >= 30 for region_id in r.region_ids)


def test_region_missing_from_stated_city_is_reported_not_swapped():
    r = resolve(city_names=["العقبة"], region_names=["خلدا"])
    assert r.city_id == AQABA
    assert r.region_ids == []
    assert r.not_found == ["خلدا"]


def test_ambiguous_region_without_city_asks():
    r = resolve(region_names=["الزهور"])
    assert r.region_ids == []
    assert r.city_id is None
    assert r.ambiguous == {"الزهور": [AMMAN, IRBID]}


def test_unambiguous_region_decides_city_for_ambiguous_one():
    # خلدا only exists in Amman, so الزهور means Amman's الزهور
    r = resolve(region_names=["الزهور", "خلدا"])
    assert r.city_id == AMMAN
    assert set(r.region_ids) == {10, 11}
    assert not r.ambiguous


def test_unique_region_infers_city():
    r = resolve(region_names=["حي التركمان"])
    assert r.city_id == IRBID
    assert r.region_ids == [23]


def test_city_only():
    r = resolve(city_names=["اربد"])
    assert r.city_id == IRBID
    assert r.region_ids == []
    assert not r.not_found


def test_landmark_follows_stated_city_not_ai_city():
    # The AI places the landmark in Amman, but the user said Irbid
    r = resolve(city_names=["اربد"], landmarks=[{"name": "دوار القبة", "region": "الزهور", "city": "عمان"}])
    assert r.city_id == IRBID
    assert r.region_ids == [20]


def test_landmark_with_ai_city_and_no_stated_city():
    r = resolve(landmarks=[{"name": "دوار هيا", "region": "السكنية الثامنة", "city": "العقبة"}])
    assert r.city_id == AQABA
    assert r.region_ids == [32]


def test_landmark_without_any_city_uses_ambiguity_rules():
    r = resolve(landmarks=[{"name": "دوار ما", "region": "الحي الشرقي", "city": None}])
    assert r.ambiguous == {"الحي الشرقي": [AMMAN, IRBID]}


def test_unknown_landmark_is_reported():
    r = resolve(city_names=["عمان"], landmarks=[{"name": "دوار غير معروف", "region": None, "city": None}])
    assert r.city_id == AMMAN
    assert r.not_found == ["دوار غير معروف"]


def test_alias_is_scoped_to_city():
    # "البلد" is an alias in Aqaba and a region in Irbid
    assert resolve(city_names=["العقبة"], region_names=["البلد"]).region_ids == [31]
    assert resolve(city_names=["اربد"], region_names=["البلد"]).region_ids == [22]


def test_fuzzy_match_stays_in_city():
    r = resolve(city_names=["عمان"], region_names=["شارع الجامعة"])
    assert r.region_ids == [15]
    # Same words, different city: nothing to match, so nothing is returned
    r = resolve(city_names=["اربد"], region_names=["شارع الجامعة"])
    assert r.region_ids == []
    assert r.not_found == ["شارع الجامعة"]


def test_zone_expansion_misses_are_silent():
    r = resolve(city_names=["عمان"], soft_region_names=["خلدا", "دابوق", "عبدون"])
    assert r.region_ids == [11]
    assert not r.not_found


def test_second_stated_city_is_ignored_not_merged():
    r = resolve(city_names=["عمان", "اربد"], region_names=["الزهور"])
    assert r.city_id == AMMAN
    assert r.region_ids == [10]
    assert r.ignored_city_ids == [IRBID]


def test_match_city_variants():
    assert match_city("بعمان", CITIES) == AMMAN
    assert match_city("العاصمة", CITIES) == AMMAN
    assert match_city("محافظة اربد", CITIES) == IRBID
    assert match_city("إربد", CITIES) == IRBID
    assert match_city("العقبه", CITIES) == AQABA
    assert match_city("خلدا", CITIES) is None
    assert match_city("", CITIES) is None


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name} {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
