---
title: "One-Click Video Testimonial Collection for SaaS Founders"
type: guide
domain: automation
level: intermediate
status: active
tags: [saas, testimonials, video-collection, social-proof, landing-page]
created: "2026-04-03T14:25:04Z"
updated: "2026-04-03T14:25:04Z"
source: reddit
score: 0.72
run_id: run_20260403_142501
---

## Problem

Solo SaaS founders send Loom links via email to collect testimonials — response rates are
low (<10%) and the resulting videos are scattered. Existing tools (Testimonial.to, Vocal
Video) cost $50–$200/mo, making them unaffordable for early-stage founders.

## Target User

Solo SaaS founder with ≥10 active customers, seeking social proof for a landing page.

## Solution

A shareable link opens a mobile-friendly page where a customer records a 30–90 second video
directly in the browser (MediaRecorder API). The video uploads automatically to cloud storage
and appears in the founder's dashboard, ready to embed with a single `<iframe>` snippet.

## Revenue Model

- $15/mo (up to 50 responses)
- $49 lifetime deal (launch promotion)

## MVP Format

`landing_page` — Static page + Cloudflare Workers + R2 storage.

## Estimated Build Time

12 hours

## Validation Steps

1. Post on IndieHackers: "How do you collect video testimonials without paying $200/mo?"
2. Tweet the landing page with a free-tier offer
3. Target: 10 signups, 3 paying users within 10 days

## Tech Stack

- HTML + MediaRecorder API (browser recording)
- Cloudflare Workers + R2 (upload + storage)
- Stripe (payments)
