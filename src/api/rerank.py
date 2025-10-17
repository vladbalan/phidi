from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple
import os

try:
	import yaml  # type: ignore
except Exception:  # pragma: no cover
	yaml = None  # will fall back to defaults

try:
	from rapidfuzz import fuzz  # type: ignore
except Exception:  # pragma: no cover
	# Lightweight fallback if rapidfuzz is unavailable at import time
	class _FuzzFallback:
		@staticmethod
		def ratio(a: str, b: str) -> float:
			return 100.0 if a == b else 0.0

		@staticmethod
		def token_sort_ratio(a: str, b: str) -> float:
			return 100.0 if sorted(a.split()) == sorted(b.split()) else 0.0

	fuzz = _FuzzFallback()  # type: ignore


DEFAULT_WEIGHTS = {
	"domain_weight": 0.45,
	"name_weight": 0.30,
	"phone_weight": 0.15,
	"social_weight": 0.10,
	"min_confidence_threshold": 0.3,
}


def load_weights(path: str | None = None) -> Dict[str, float]:
	path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "weights.yaml")
	data: Dict[str, float] = {}
	if yaml and os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				y = yaml.safe_load(f) or {}
				if isinstance(y, dict):
					data.update({k: float(v) for k, v in y.items() if isinstance(v, (int, float))})
		except Exception:
			pass
	# Merge defaults for any missing
	merged = {**DEFAULT_WEIGHTS, **data}
	# Normalize weight values (but not threshold) to 1.0 if sum deviates significantly
	weight_keys = ["domain_weight", "name_weight", "phone_weight", "social_weight"]
	s = sum(merged.get(k, 0.0) for k in weight_keys)
	if s > 0 and abs(s - 1.0) > 1e-6:
		for k in weight_keys:
			if k in merged:
				merged[k] = merged[k] / s
	return merged


def score_candidate(inp: Dict[str, Any], cand: Dict[str, Any], weights: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
	scores: Dict[str, float] = {}

	# Domain exact or fuzzy ratio
	in_domain = inp.get("domain") or ""
	cand_domain = (cand.get("domain") or "").strip()
	if in_domain and cand_domain:
		if in_domain == cand_domain:
			scores["domain"] = 1.0
		else:
			try:
				scores["domain"] = float(fuzz.ratio(in_domain, cand_domain)) / 100.0
			except Exception:
				scores["domain"] = 0.0
	else:
		scores["domain"] = 0.0

	# Name fuzzy match (case-insensitive)
	# Use hybrid approach: max of multiple algorithms to handle various name patterns
	# - ratio: simple character matching
	# - token_sort_ratio: handles word order differences
	# - partial_ratio: handles merged words and substrings
	in_name = (inp.get("company_name") or "").strip().lower()
	cand_name = ((cand.get("company_name") or cand.get("name") or "").strip().lower())
	try:
		if in_name and cand_name:
			simple_score = float(fuzz.ratio(in_name, cand_name)) / 100.0
			token_score = float(fuzz.token_sort_ratio(in_name, cand_name)) / 100.0
			partial_score = float(fuzz.partial_ratio(in_name, cand_name)) / 100.0
			# Take the maximum to be most generous and handle edge cases
			scores["name"] = max(simple_score, token_score, partial_score)
		else:
			scores["name"] = 0.0
	except Exception:
		scores["name"] = 1.0 if in_name == cand_name and in_name else 0.0

	# Phone exact: input phone must be contained in candidate phones (array)
	in_phone = inp.get("phone")
	cand_phones = cand.get("phones") or []
	scores["phone"] = 1.0 if in_phone and isinstance(cand_phones, list) and in_phone in cand_phones else 0.0

	# Social exact: check facebook and instagram
	# Only score when BOTH input and candidate have the field (avoids false penalties)
	in_fb = inp.get("facebook")
	cand_fb = cand.get("facebook")
	in_ig = inp.get("instagram")
	cand_ig = cand.get("instagram")
	
	social_scores: List[float] = []
	if in_fb and cand_fb:
		social_scores.append(1.0 if in_fb == cand_fb else 0.0)
	if in_ig and cand_ig:
		social_scores.append(1.0 if in_ig == cand_ig else 0.0)
	
	# If no comparable social fields, treat as neutral (0.5) rather than penalizing
	scores["social"] = sum(social_scores) / len(social_scores) if social_scores else 0.5

	final = (
		scores.get("domain", 0.0) * weights.get("domain_weight", 0.0)
		+ scores.get("name", 0.0) * weights.get("name_weight", 0.0)
		+ scores.get("phone", 0.0) * weights.get("phone_weight", 0.0)
		+ scores.get("social", 0.0) * weights.get("social_weight", 0.0)
	)
	return float(final), scores


def rerank_candidates(inp: Dict[str, Any], candidates: Iterable[Dict[str, Any]], weights_path: str | None = None) -> List[Dict[str, Any]]:
	weights = load_weights(weights_path)
	ranked: List[Dict[str, Any]] = []
	for c in candidates:
		score, breakdown = score_candidate(inp, c, weights)
		ranked.append({"candidate": c, "score": score, "breakdown": breakdown})
	ranked.sort(key=lambda x: x["score"], reverse=True)
	return ranked

