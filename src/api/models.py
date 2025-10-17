from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class CompanyInput(BaseModel):
	company_name: str = Field(..., min_length=1, description="Company name as provided by user")
	website: Optional[str] = Field(None, description="Company website or domain")
	phone_number: Optional[str] = Field(None, description="Company phone number in any format")
	facebook_url: Optional[str] = Field(None, description="Facebook page URL (optional)")
	instagram_url: Optional[str] = Field(None, description="Instagram page URL (optional)")

	@field_validator("company_name")
	@classmethod
	def validate_company_name(cls, v: str) -> str:
		"""Validate company name is not empty or whitespace-only."""
		if not v or not v.strip():
			raise ValueError("company_name must not be empty or whitespace-only")
		return v

	@model_validator(mode="after")
	def validate_minimum_fields(self) -> "CompanyInput":
		"""Validate that at least one field (name, website, phone, or social) has meaningful data.
		
		This ensures the API receives enough information to perform a reasonable match.
		Empty strings and whitespace-only values don't count as meaningful data.
		"""
		# Check if any field has meaningful (non-empty, non-whitespace) data
		has_name = bool(self.company_name and self.company_name.strip())
		has_website = bool(self.website and self.website.strip())
		has_phone = bool(self.phone_number and self.phone_number.strip())
		has_facebook = bool(self.facebook_url and self.facebook_url.strip())
		has_instagram = bool(self.instagram_url and self.instagram_url.strip())
		
		# Count meaningful fields (name is already validated, so it counts)
		meaningful_fields = sum([has_name, has_website, has_phone, has_facebook, has_instagram])
		
		if meaningful_fields < 1:
			raise ValueError(
				"At least one field with meaningful data is required for matching. "
				"Provide company_name, website, phone_number, facebook_url, or instagram_url."
			)
		
		return self


class Address(BaseModel):
	street: Optional[str] = None
	city: Optional[str] = None
	state: Optional[str] = None
	zip: Optional[str] = None


class CompanyResult(BaseModel):
	domain: Optional[str] = None
	company_name: Optional[str] = None
	phones: List[str] = Field(default_factory=list)
	facebook: Optional[str] = None
	linkedin: Optional[str] = None
	twitter: Optional[str] = None
	instagram: Optional[str] = None
	address: Optional[Address] = None


class MatchResponse(BaseModel):
	match_found: bool
	confidence: float = Field(0.0, ge=0.0, le=1.0)
	company: Optional[CompanyResult] = None
	score_breakdown: Dict[str, float] = Field(default_factory=dict)

