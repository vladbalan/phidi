import os
import json
from typing import Any, Dict, List

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, PlainTextResponse

from src.api.models import CompanyInput, CompanyResult, MatchResponse
from src.api.query_es import search_candidates, build_query, ES_URL, ES_INDEX
from src.api.rerank import rerank_candidates, load_weights
from src.api.metrics import track_request, match_confidence_distribution, matches_found_total

from src.common.domain_utils import clean_domain
from src.common.phone_utils import normalize_phone
from src.common.social_utils import canonicalize_facebook, canonicalize_instagram

try:
	from prometheus_client import generate_latest, CONTENT_TYPE_LATEST  # type: ignore
except Exception:  # pragma: no cover
	generate_latest = None  # type: ignore
	CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


app = FastAPI(title="Company Matching API", version="0.1.0")


# Debug toggle
API_DEBUG = os.getenv("API_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def _dbg(label: str, payload: Any | None = None) -> None:
	"""Lightweight debug printer controlled by API_DEBUG env var.

	Prints a single line per call, prefixed to make grepping easy. Objects are JSON-encoded
	when possible, falling back to str().
	"""
	if not API_DEBUG:
		return
	try:
		msg = label if payload is None else f"{label}: {json.dumps(payload, ensure_ascii=False, default=str)}"
	except Exception:
		msg = label if payload is None else f"{label}: {payload}"
	print(f"[API-DEBUG] {msg}")


@app.get("/healthz")
async def healthz():
	return {"status": "ok"}


@app.get("/metrics")
async def metrics():
	if generate_latest is None:
		return PlainTextResponse("prometheus_client not installed", status_code=503)
	data = generate_latest()  # type: ignore
	return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.post("/match")
@track_request
async def match_company(payload: CompanyInput = Body(...)):
	try:
		# Step 1: Normalize input
		normalized_input: Dict[str, Any] = {
			"company_name": (payload.company_name or "").strip().lower(),
			"domain": clean_domain(payload.website),
			"phone": normalize_phone(payload.phone_number),
			"facebook": canonicalize_facebook(payload.facebook_url),
			"instagram": canonicalize_instagram(payload.instagram_url),
		}

		_dbg("incoming.payload", payload.model_dump())
		_dbg("normalized.input", normalized_input)

		# Build and log ES query details for transparency
		query_body = build_query(
			company_name=normalized_input.get("company_name"),
			domain=normalized_input.get("domain"),
			phone=normalized_input.get("phone"),
			facebook=normalized_input.get("facebook"),
			instagram=normalized_input.get("instagram"),
		)
		_dbg("es.config", {"url": ES_URL, "index": ES_INDEX})
		_dbg("es.query", query_body)

		# Step 2: Retrieve candidates from Elasticsearch
		candidates = search_candidates(normalized_input, size=10)
		_dbg("es.candidates.count", len(candidates))
		if candidates:
			preview: List[Dict[str, Any]] = []
			for c in candidates[:3]:
				preview.append({
					"domain": c.get("domain"),
					"company_name": c.get("company_name") or c.get("name"),
					"phones": c.get("phones"),
					"facebook": c.get("facebook"),
				})
			_dbg("es.candidates.preview", preview)

		# Step 3: Rerank candidates
		ranked = rerank_candidates(normalized_input, candidates)
		if ranked:
			_dbg("rerank.top.score", ranked[0].get("score"))
			_dbg("rerank.top.breakdown", ranked[0].get("breakdown"))
		else:
			_dbg("rerank.result", "no candidates to rank")

		# Step 4: Build response
		if ranked:
			top = ranked[0]
			conf = float(top["score"]) if isinstance(top.get("score"), (int, float)) else 0.0
			
			# Load config to get minimum confidence threshold
			config = load_weights()
			min_threshold = config.get("min_confidence_threshold", 0.3)
			
			# Reject matches below confidence threshold
			if conf < min_threshold:
				_dbg("match.result", {"match_found": False, "reason": f"confidence {conf:.4f} below threshold {min_threshold}"})
				return JSONResponse(content={"match_found": False, "confidence": conf, "company": None, "score_breakdown": top.get("breakdown", {})})
			
			match_confidence_distribution.observe(conf)
			level = "high" if conf >= 0.9 else ("medium" if conf >= 0.7 else "low")
			matches_found_total.labels(confidence_level=level).inc()

			cand = top["candidate"]
			body = {
				"match_found": True,
				"confidence": conf,
				"company": {
					"domain": cand.get("domain"),
					"company_name": cand.get("company_name") or cand.get("name"),
					"phones": cand.get("phones") or [],
					"facebook": cand.get("facebook"),
					"linkedin": cand.get("linkedin"),
					"twitter": cand.get("twitter"),
					"instagram": cand.get("instagram"),
					"address": cand.get("address"),
				},
				"score_breakdown": top.get("breakdown", {}),
			}
			return JSONResponse(content=body)

		# No candidates or no ES available
		_dbg("match.result", {"match_found": False, "reason": "no candidates or exception"})
		return JSONResponse(content={"match_found": False, "confidence": 0.0, "company": None, "score_breakdown": {}})
	except Exception:
		# Fail safe: never 500 on this endpoint; return no-match instead
		_dbg("match.exception", "unexpected error; returning no-match")
		return JSONResponse(content={"match_found": False, "confidence": 0.0, "company": None, "score_breakdown": {}})


def get_uvicorn_app():  # for uvicorn:app
	return app

