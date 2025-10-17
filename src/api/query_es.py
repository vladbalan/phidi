from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
import time

try:
	from elasticsearch import Elasticsearch  # type: ignore
except Exception:  # pragma: no cover
	Elasticsearch = None  # type: ignore

from src.api.metrics import es_query_duration, es_candidates_retrieved


ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_ALIAS", os.getenv("ES_INDEX", "companies_v1"))


def build_query(company_name: Optional[str], domain: Optional[str], phone: Optional[str], facebook: Optional[str], instagram: Optional[str] = None) -> Dict[str, Any]:
	should: List[Dict[str, Any]] = []
	if domain:
		should.append({"term": {"domain": {"value": domain, "boost": 10.0}}})
	if company_name:
		should.append({"match": {"company_name": {"query": company_name, "boost": 5.0}}})
	if phone:
		should.append({"term": {"phones": {"value": phone, "boost": 3.0}}})
	if facebook:
		should.append({"term": {"facebook": {"value": facebook, "boost": 2.0}}})
	if instagram:
		should.append({"term": {"instagram": {"value": instagram, "boost": 2.0}}})

	return {
		"bool": {
			"should": should or [{"match_all": {}}],
			"minimum_should_match": 1 if should else 0,
		}
	}


def search_candidates(params: Dict[str, Any], size: int = 10) -> List[Dict[str, Any]]:
	query = build_query(
		company_name=params.get("company_name"),
		domain=params.get("domain"),
		phone=params.get("phone"),
		facebook=params.get("facebook"),
		instagram=params.get("instagram"),
	)

	start = time.time()
	try:
		if Elasticsearch is None:
			raise RuntimeError("elasticsearch package not available")
		es = Elasticsearch(ES_URL)
		resp = es.search(index=ES_INDEX, body={"query": query, "size": size})
		hits = (resp or {}).get("hits", {}).get("hits", [])
		candidates: List[Dict[str, Any]] = []
		for h in hits:
			src = h.get("_source", {})
			if isinstance(src, dict):
				candidates.append(src)
		return candidates
	except Exception:
		# Fallback: return empty list if ES unavailable
		return []
	finally:
		duration = time.time() - start
		es_query_duration.observe(duration)
		# Bucketing number of candidates
		try:
			es_candidates_retrieved.observe(float(len(locals().get("hits", []))))
		except Exception:
			pass

