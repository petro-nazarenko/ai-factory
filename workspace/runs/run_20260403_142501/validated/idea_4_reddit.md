---
title: "Brief-to-Proposal Formatter for Freelance Copywriters"
type: guide
domain: automation
level: beginner
status: active
tags: [freelance, copywriting, proposal-automation, claude-api, google-forms]
created: "2026-04-03T14:25:04Z"
updated: "2026-04-03T14:25:04Z"
source: reddit
score: 0.85
run_id: run_20260403_142501
---

## Problem

Freelance copywriters spend 45+ minutes manually reformatting client briefs into polished
proposals using Google Docs templates — a repetitive, low-value task blocking paid work.

## Target User

Freelance copywriter with recurring client intake (5–20 projects/month).

## Solution

A Google Form collects the brief fields (client name, project type, goals, tone, deadline,
budget). On submit, a Claude API call formats the inputs into a ready-to-send proposal using
a proven template. Output is emailed to the copywriter within 60 seconds.

## Revenue Model

- Pay-per-use: $1.50/proposal
- Monthly flat: $19/mo unlimited

## MVP Format

`google_form_manual` — Google Form + Apps Script + Claude API. No infra required.

## Estimated Build Time

4 hours

## Validation Steps

1. Post in r/freelancewriters: "Would you pay $1.50 to auto-generate proposals from a form?"
2. DM 10 copywriters on LinkedIn with a free trial link
3. Target: 3 paying users within 7 days

## Tech Stack

- Google Forms + Apps Script
- Anthropic Claude API (claude-haiku-4-5)
- Gmail (output delivery)
