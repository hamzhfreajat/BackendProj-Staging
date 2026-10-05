"""
Location resolver for the smart search.

Pure logic (no DB access) so it can be unit tested: the caller loads cities,
regions and aliases once and passes them in.

Rules:
  1. The city the user stated always wins. Regions and landmarks are only
     looked up inside it, never in another city.
  2. Without a stated city, a region name that exists in exactly one city
     infers that city. A name that exists in several cities is reported as
     ambiguous so the caller can ask the user to write the city.
  3. Landmarks are not stored in the DB. The AI suggests the region (and city)
     a landmark belongs to, and that suggestion is validated here like any
     other region name.
"""
import difflib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from arabic_utils import normalize_arabic

REGION_FUZZY_THRESHOLD = 0.75
CITY_FUZZY_THRESHOLD = 0.85

# Ways users refer to a city that differ from its name in the DB
CITY_SYNONYMS = {
    "عاصمه": "عمان",
    "محافظه عاصمه": "عمان",
}


@dataclass
class LocationResolution:
    city_id: Optional[int] = None
    region_ids: List[int] = field(default_factory=list)
    # Names the user wrote that match nothing (inside the city, when one is known)
    not_found: List[str] = field(default_factory=list)
    # name -> ids of the cities that have a region with that name
    ambiguous: Dict[str, List[int]] = field(default_factory=dict)
    # Cities the user stated beyond the first one (only one city is searched)
    ignored_city_ids: List[int] = field(default_factory=list)


def _norm_city(name: str) -> str:
    norm = normalize_arabic(name or "")
    if norm.startswith("محافظه ") and norm not in CITY_SYNONYMS:
        norm = norm[len("محافظه "):]
    return normalize_arabic(CITY_SYNONYMS.get(norm, norm))


def match_city(name: str, cities: Iterable[Tuple[int, str]]) -> Optional[int]:
    """cities: (id, name_ar). Returns the id of the city `name` refers to, if any."""
    norm = _norm_city(name)
    if not norm:
        return None
    best_id, best_score = None, 0.0
    for city_id, city_name in cities:
        city_norm = normalize_arabic(city_name)
        if norm == city_norm:
            return city_id
        score = difflib.SequenceMatcher(None, norm, city_norm).ratio()
        if score > best_score:
            best_id, best_score = city_id, score
    return best_id if best_score > CITY_FUZZY_THRESHOLD else None


def _fuzzy_score(norm_loc: str, db_norm: str) -> float:
    score = difflib.SequenceMatcher(None, norm_loc, db_norm).ratio()
    # Boost when one name contains the other (helps long names like
    # "شارع الجامعة (الجامعة الأردنية)")
    if (norm_loc in db_norm or db_norm in norm_loc) and len(norm_loc) > 4:
        substring_ratio = min(len(norm_loc), len(db_norm)) / max(len(norm_loc), len(db_norm))
        score = max(score, 0.85 + substring_ratio * 0.14)
    return score


class _Index:
    def __init__(self, regions, aliases):
        # regions: (id, city_id, name_ar) / aliases: (alias_name, region_id)
        self.regions = [(r_id, city_id, normalize_arabic(name)) for r_id, city_id, name in regions]
        self.city_of = {r_id: city_id for r_id, city_id, _ in self.regions}
        self.aliases = [
            (normalize_arabic(alias), region_id)
            for alias, region_id in aliases
            if region_id in self.city_of
        ]

    def candidates(self, name: str, city_id: Optional[int] = None, allow_fuzzy: bool = True) -> List[int]:
        """Region ids matching `name`, limited to `city_id` when given.
        Exact name first, then exact alias, then the best fuzzy match(es)."""
        norm = normalize_arabic(name or "")
        if not norm:
            return []
        in_scope = [r for r in self.regions if city_id is None or r[1] == city_id]

        exact = [r_id for r_id, _, r_norm in in_scope if r_norm == norm]
        if exact:
            return exact

        by_alias = [
            region_id for alias_norm, region_id in self.aliases
            if alias_norm == norm and (city_id is None or self.city_of[region_id] == city_id)
        ]
        if by_alias:
            return list(dict.fromkeys(by_alias))

        if not allow_fuzzy:
            return []

        scored = [(_fuzzy_score(norm, r_norm), r_id) for r_id, _, r_norm in in_scope]
        if not scored:
            return []
        best = max(score for score, _ in scored)
        if best <= REGION_FUZZY_THRESHOLD:
            return []
        # Keep ties: the same name in two cities scores the same and must stay ambiguous
        return [r_id for score, r_id in scored if best - score < 1e-9]


def resolve_locations(
    cities: List[Tuple[int, str]],
    regions: List[Tuple[int, int, str]],
    aliases: List[Tuple[str, int]],
    city_names: Optional[List[str]] = None,
    region_names: Optional[List[str]] = None,
    landmarks: Optional[List[dict]] = None,
    soft_region_names: Optional[List[str]] = None,
) -> LocationResolution:
    """
    city_names: cities the user stated.
    region_names: regions/neighbourhoods the user stated (may still contain a city).
    landmarks: [{"name": ..., "region": ..., "city": ...}] where region/city are the AI's suggestion.
    soft_region_names: expansions we added ourselves (e.g. "غرب عمان"); misses are not reported.
    """
    result = LocationResolution()
    index = _Index(regions, aliases)

    # 1. Stated cities. A city can also show up inside the regions list.
    stated_city_ids = []
    for name in city_names or []:
        c_id = match_city(name, cities)
        if c_id is not None:
            stated_city_ids.append(c_id)
    plain_regions = []
    for name in region_names or []:
        if not normalize_arabic(name or ""):
            continue
        c_id = match_city(name, cities)
        if c_id is not None:
            stated_city_ids.append(c_id)
        else:
            plain_regions.append(name)
    stated_city_ids = list(dict.fromkeys(stated_city_ids))
    if stated_city_ids:
        result.city_id = stated_city_ids[0]
        result.ignored_city_ids = stated_city_ids[1:]

    # Landmarks: with no city to anchor them, the AI's region is treated like
    # a region the user wrote, so the ambiguity rules below apply to it too.
    anchored_landmarks = []
    for lm in landmarks or []:
        if not isinstance(lm, dict):
            continue
        lm_name = str(lm.get("name") or "").strip()
        lm_region = str(lm.get("region") or "").strip()
        if not lm_name and not lm_region:
            continue
        lm_city_id = match_city(str(lm.get("city") or ""), cities)
        if result.city_id is None and lm_city_id is None:
            plain_regions.append(lm_region or lm_name)
        else:
            anchored_landmarks.append((lm_name, lm_region, lm_city_id))

    found: List[int] = []

    # 2. Regions
    if result.city_id is not None:
        for name in plain_regions:
            cands = index.candidates(name, city_id=result.city_id)
            if cands:
                found.append(cands[0])
            else:
                result.not_found.append(name)
    else:
        resolved = []   # (name, region_id) for names living in exactly one city
        pending = []    # (name, candidate region ids) for names living in several cities
        for name in plain_regions:
            cands = index.candidates(name)
            cand_cities = list(dict.fromkeys(index.city_of[r] for r in cands))
            if not cands:
                result.not_found.append(name)
            elif len(cand_cities) == 1:
                resolved.append((name, cands[0]))
            else:
                pending.append((name, cands))

        if resolved:
            # The unambiguous regions decide the city
            result.city_id = index.city_of[resolved[0][1]]
            for name, r_id in resolved:
                if index.city_of[r_id] == result.city_id:
                    found.append(r_id)
                else:
                    result.not_found.append(name)
            for name, cands in pending:
                in_city = [r for r in cands if index.city_of[r] == result.city_id]
                if in_city:
                    found.append(in_city[0])
                else:
                    result.not_found.append(name)
        else:
            for name, cands in pending:
                result.ambiguous[name] = list(dict.fromkeys(index.city_of[r] for r in cands))

    # 3. Landmarks that have a city to anchor them
    for lm_name, lm_region, lm_city_id in anchored_landmarks:
        if result.ambiguous:
            break
        scope_city = result.city_id if result.city_id is not None else lm_city_id
        # The landmark itself may be a known region or alias; otherwise use the AI's region
        cands = index.candidates(lm_name, city_id=scope_city, allow_fuzzy=False)
        if not cands and lm_region:
            cands = index.candidates(lm_region, city_id=scope_city)
        if cands:
            found.append(cands[0])
            if result.city_id is None:
                result.city_id = scope_city
        else:
            result.not_found.append(lm_name or lm_region)

    # 4. Our own expansions, only inside the resolved city
    if result.city_id is not None and not result.ambiguous:
        for name in soft_region_names or []:
            cands = index.candidates(name, city_id=result.city_id, allow_fuzzy=False)
            if cands:
                found.append(cands[0])

    result.region_ids = list(dict.fromkeys(found))
    result.not_found = list(dict.fromkeys(result.not_found))
    return result
