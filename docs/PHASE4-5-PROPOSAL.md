# Mann Made Media Platform - Phase 4 & 5 Proposal

**Prepared by:** Mann Made Executive Team (Zara, Leo, Nova, Finn, Kai)
**Date:** March 11, 2026
**Platform:** Mann Made Media Platform (localhost:7070)
**Status:** Internal tool, Phase 3 complete

---

## Executive Summary (Zara - CEO)

### What this platform is right now

We have a working social publishing tool. 114 posts tracked, 63 on X and 51 on LinkedIn, 54 posts in the past week. Only 2 of 10 configured accounts are actively posting (mic-x and mic-linkedin). The other 8 accounts - Mann Made, PodPal, Singularity SA, Facebook, Instagram, TikTok, YouTube - are connected but idle. That is the gap we fix in Phase 4.

This is not a toy. A tool that posts 54 times a week, tracks every post, and prevents duplicates is already more disciplined than most agencies. The question is whether we keep it as an internal productivity tool or turn it into a product.

### What it could become in 90 days

In 90 days, this platform should be doing three things it cannot do today:

1. Publishing across all 10 accounts, not just 2
2. Generating content with AI so Mic spends 20 minutes a day on social instead of 2 hours
3. Managing at least one external client's social presence, with a white-label portal they can log into

That is the difference between a personal tool and an agency product.

### Where it sits in the Mann Made portfolio

Mann Made runs two products: PodPal (podcast production and distribution) and this platform (social publishing). These are not competitors. They are a pipeline.

PodPal creates content. This platform distributes it. A podcast episode becomes an X thread, a LinkedIn post, a short clip, a carousel - all pushed from one place. The integration play in Phase 5 is connecting these two systems so content flows automatically from recording to distribution.

### Top 3 strategic bets

1. **AI content generation** - The biggest time sink right now is writing posts. If the platform can generate 80% of the content from a URL, topic, or podcast transcript, Mic gets leverage and clients get a reason to pay monthly.

2. **Client portal** - Mann Made already serves clients. Giving them a branded portal to approve posts, see their calendar, and review analytics turns a service into a SaaS line item. This is recurring revenue.

3. **Full account activation** - 8 dormant accounts is a waste. Activating Instagram, TikTok, Facebook, and the brand accounts multiplies reach without proportionally increasing workload. Phase 4 makes this possible.

---

## Phase 4 Proposal

Phase 4 is about three things: generate content, distribute it to all platforms, and build the client-facing layer. Here is what we are building.

### 4A - AI Content Generation (Priority 1)

**The problem:** Writing 54 posts a week manually is not scalable. When you add clients, it becomes impossible.

**What we build:**

A "Generate" tab in the new post modal. Input options:
- Paste a URL (article, podcast episode, LinkedIn post) - platform extracts key ideas and generates 3-5 post variations per platform
- Type a topic ("AI in Africa", "PodPal launch") - generates a week's worth of posts
- Upload a transcript - extracts quotes, insights, and talking points, formats per platform

**Tone matching per account:** Each account in accounts.json gets a `tone` field:
- mic-x: concise, provocative, first-person
- mic-linkedin: narrative, reflective, longer form
- mannmade-x: brand voice, agency perspective
- podpal-x: podcast promo, guest hooks

The AI respects these tones. A Mic Mann X post and a Mann Made X post on the same topic read differently.

**Batch calendar fill:** Select a date range, pick a topic or campaign, and the platform generates a full calendar of scheduled posts across selected accounts. Review and approve in bulk.

**Model recommendation:** Use Claude Sonnet via OpenClaw. Cost is negligible at this volume. No external API key needed beyond what OpenClaw already has.

**What this unlocks:** Mic goes from 2 hours/day writing to 20 minutes reviewing. Clients can be onboarded without a content team.

---

### 4B - Client Portal (Priority 2)

**The problem:** There is no way to manage a client's social presence without giving them access to Mic's entire platform.

**What we build:**

A `/client` route in server.py with a separate authentication layer. Each client gets:
- A unique login (email + password, stored locally or via a simple auth table)
- A view of only their accounts and posts
- A calendar showing scheduled and posted content
- An approval workflow: the platform generates or drafts content, the client approves or requests edits before it goes live
- A basic analytics view (posts this week, platform breakdown)

**White-label:** Client portals show the client's logo, not Mann Made's. A simple `branding` object per client in a `clients.json` file controls colours, logo URL, and company name.

**Approval flow:**
- Mann Made drafts content, marks it "pending approval"
- Client logs in, sees their queue, clicks approve or requests changes
- Approved posts go into the scheduled queue automatically
- Mann Made is notified of any change requests via a simple notification in the main dashboard

**This is the recurring revenue feature.** Everything else is productivity. This is the product.

---

### 4C - Full Platform Activation (Priority 3)

**The problem:** 8 of 10 accounts are idle. Instagram, TikTok, Facebook, and all brand accounts are configured but not posting.

**What we build:**

- Fix or reactivate browser sessions for all 8 inactive accounts
- Platform-specific post formatting: Instagram needs images, TikTok needs video or carousels, Facebook is more flexible
- Media attachment support improvements: when posting to Instagram/TikTok, the platform prompts for or auto-generates a compatible image
- Cross-post mode: write once, push to all selected accounts with platform-appropriate formatting

**Singularity SA account specifically:** This account (@singularitysa) is under-used. It should be posting 3-5x per week on AI, exponential tech, and SUSA Summit content. The AI generation feature (4A) makes this trivial to maintain.

---

### 4D - Content Templates (Priority 4)

**The problem:** Certain post types repeat. Podcast promo, Monday motivation, weekly roundup, event announcement. Writing them from scratch every time is waste.

**What we build:**

A Templates section in the UI. Each template has:
- Name (e.g., "PodPal Guest Promo")
- Platform(s) it applies to
- Template text with placeholders: `{guest_name}`, `{episode_topic}`, `{link}`
- Default accounts to post to

Creating a new post from a template pre-fills the content and accounts. User fills in the variables and posts.

**30 minutes of setup replaces hours of writing per month.**

---

## Phase 5 Proposal

Phase 5 is the bigger bet. It turns Mann Made Media Platform into a standalone product that competes with Buffer, Hootsuite, and Later - but built for Africa, agencies, and AI-first workflows.

### 5A - PodPal Integration

PodPal produces podcast episodes. This platform distributes content. Connect them.

When a PodPal episode is published:
- Platform receives a webhook with the transcript and episode metadata
- AI generates a full social campaign: X thread, LinkedIn post, short quote clips, audiogram description
- Campaign is queued for review and approval
- Mic or the client approves it, scheduled posts go out across all platforms

This turns a single podcast episode into 10-15 social posts with zero manual writing.

### 5B - Engagement Monitoring

Pull comments and replies from X and LinkedIn into a single inbox. Reply from the platform without switching tabs. Flag high-value comments (potential clients, media inquiries) for priority response.

This is a force multiplier. Right now, social engagement happens reactively. An engagement inbox makes it systematic.

### 5C - Hashtag and Trend Intelligence

Pull trending topics from X per region (South Africa, Africa, global tech) each morning. Surface the 5 most relevant to Mic's audience. When generating content, the platform suggests hashtags based on what is actually performing.

This is a thin layer on top of the X API or scraping - not a big build, but a high-value daily touchpoint.

### 5D - White-Label SaaS Launch

Package the client portal (Phase 4B) as a standalone SaaS product. Other South African agencies can subscribe and manage their clients through the same system. Mann Made becomes both an agency and a software company.

Pricing and go-to-market are covered in the Revenue Model section.

### 5E - Ad Spend Tracking

Connect Meta Ads API and LinkedIn Ads API. Show campaign ROI alongside organic post performance. Answer the question: "Is our R5,000 Facebook spend working?"

This is a Phase 5 feature because it requires API access that takes time to set up, and its value is highest once clients are already on the platform through Phase 4.

---

## Revenue Model (Finn - CFO)

### Can this be sold as SaaS?

Yes. The architecture is already single-tenant. Making it multi-tenant is a development sprint, not a rebuild. The client portal (Phase 4B) is the SaaS foundation.

### Pricing tiers

**Agency Internal (current state):** R0 - internal tool, Mann Made uses it to serve clients. Value realised through client billing, not platform fees.

**Agency Starter - R1,500/month per client:**
- Up to 3 social accounts
- Content calendar and queue
- Basic analytics
- Client approval portal
- 5 AI-generated posts per week

**Agency Growth - R3,500/month per client:**
- Up to 10 social accounts
- Unlimited AI content generation
- Hashtag intelligence
- Engagement inbox
- Priority support

**Platform SaaS (Phase 5 launch) - for other agencies:**
- Starter: R2,500/month (up to 3 client workspaces)
- Growth: R6,000/month (up to 10 client workspaces)
- Scale: R12,000/month (unlimited client workspaces, white-label branding)

### Revenue projections (conservative)

If Mann Made signs 5 clients on Agency Starter by end of Phase 4:
- Monthly recurring: R7,500
- Annually: R90,000

If 3 external agencies adopt the Platform SaaS on Growth tier by end of Phase 5:
- Monthly recurring: R18,000 additional
- Annually: R216,000

These are not big numbers yet. But they are recurring, they grow with clients, and they come from infrastructure that is already mostly built.

### Integration with PodPal revenue

PodPal clients who also use the media platform get a bundled rate. A podcaster paying for PodPal production gets social distribution included at R800/month add-on. This increases PodPal retention (stickier product) and adds revenue without a new sales motion.

Target: 30% of PodPal clients convert to the social add-on within 6 months of launch.

---

## Leo's Sales Angle (CSO)

### Top 3 client types who would pay today

**1. Personal brands and thought leaders (R1,500-R2,500/month)**
Founders, executives, speakers who need a consistent social presence but do not have time to write content. They have the ideas. They need the execution. AI generation plus a posting calendar is exactly what they will pay for. Mic is the case study.

**2. South African SMEs with multiple social accounts (R2,000-R3,500/month)**
A restaurant group, a retail chain, or a professional services firm managing 3-5 social accounts with no dedicated social person. They are currently using Hootsuite at R800/month and getting nothing tailored to SA. A locally-built tool with AI that understands their market is a compelling switch.

**3. Other digital agencies (Platform SaaS - R6,000-R12,000/month)**
Agencies that manage social for 5-20 clients and are doing it manually or with generic tools. They do not want to build their own platform. They want to white-label ours and charge their clients a markup. This is the highest-leverage play.

### The pitch (2 sentences)

Mann Made Media Platform manages your social presence across every platform from one dashboard, generates content with AI, and lets your clients approve posts before they go live. It is built for South African agencies who are tired of paying for tools that do not understand their market.

### First 5 prospects

1. **Singularity SA community partners** - Companies already in the SUSA ecosystem who need social amplification around the Summit and AI topics. Warm introduction via Mic.

2. **PodPal podcast clients** - Anyone using PodPal for their podcast who does not have a social strategy for their episodes. Bundle offer, low-friction sell.

3. **Braamfontein/Sandton founder network** - Founders Mic interacts with who have strong ideas but inconsistent social presence. Offer a 30-day trial and let the AI content speak for itself.

4. **One mid-size SA digital agency** - Approach an agency that is not a direct Mann Made competitor. Pitch the white-label platform angle. One agency client at R6,000/month is more valuable than three individual clients.

5. **Local tech startups preparing for fundraise** - Startups need a strong social presence before approaching investors. Short-term, high-urgency client. Offer a 3-month package.

---

## Nova's Content Gaps (CMO)

### What is missing that would 10x the value

**1. Visual content generation**
Every post right now is text. Instagram and TikTok require images or video. Without visual content, 3 of 10 accounts are effectively dead. Phase 4 must include at minimum: AI image generation for posts (via Gemini or OpenAI image APIs), template-based carousel creation, and audiogram generation for podcast clips.

**2. Cross-platform content adaptation**
Writing a LinkedIn post is not the same as writing an X post. Currently there is no enforcement of this. A 400-word LinkedIn piece gets posted verbatim to X. The AI generation layer (Phase 4A) needs to automatically adapt content length, tone, and format per platform. LinkedIn: narrative, 150-400 words, no hashtag spam. X: punchy, under 280 characters for the hook, thread format for depth. TikTok captions: short, hook-first, 3-5 hashtags.

**3. Content performance feedback loop**
Analytics currently shows posts over time and platform breakdown. What it does not show: which posts performed best, what topics drove the most engagement, which posting times work for which platform. Without this, content strategy is guesswork. Phase 4 analytics should pull engagement data (likes, reposts, comments) from X and LinkedIn and surface: top 5 posts this month, best posting time by platform, topic clusters that outperform.

**4. Campaign management**
Right now posts live in isolation. There is no concept of a campaign - a series of posts built around a launch, an event, or a topic thread. A campaign view would show: all posts related to the SUSA Summit, for example, their status, which accounts they went to, and combined performance.

**5. Content idea bank**
A simple list where Mic or team members can drop ideas, URLs, quotes, or rough thoughts. The AI picks from this bank when generating content. Currently ideas live in notes apps or disappear. Centralising them in the platform creates a content flywheel.

### AI writing recommendations

Use Claude Sonnet for standard post generation (cost-effective, high quality). Use Claude Opus only for long-form LinkedIn articles or campaign strategy documents. Build a system prompt per account that encodes Mic's voice, banned phrases, topic preferences, and posting rules. The system prompt should include examples of Mic's best posts (pull the top performers from posted_tracker.json once engagement data is available).

---

## Build Priority Matrix

| Feature | Impact | Effort | Revenue Potential | Build First? |
|---|---|---|---|---|
| AI content generation (4A) | H | M | H | Yes - Week 1-2 |
| Content templates (4D) | H | L | M | Yes - Week 1 |
| Full account activation (4C) | H | M | M | Yes - Week 2 |
| Client portal + approval flow (4B) | H | H | H | Yes - Week 3-4 |
| Content performance analytics | H | M | H | Phase 4 tail / Phase 5 |
| Visual content generation | H | H | H | Phase 5 |
| Campaign management | M | M | M | Phase 5 |
| Content idea bank | M | L | L | Phase 4 tail |
| Cross-platform adaptation | H | L | M | Include in 4A |
| PodPal integration | H | M | H | Phase 5 |
| Engagement monitoring inbox | M | M | M | Phase 5 |
| Hashtag and trend intelligence | M | L | M | Phase 5 |
| Ad spend tracking | M | H | H | Phase 5 |
| Platform SaaS white-label | H | H | H | Phase 5 |

---

## Implementation Plan - Phase 4 (4 Weeks)

### Week 1: AI Content Generation Core + Templates

**Goal:** Mic can generate a week of posts from a URL or topic in under 5 minutes.

- Add "Generate" tab to new post modal in index.html
- Build `/api/generate` endpoint in server.py: accepts URL or topic, calls Claude via shell/API, returns 3-5 post variations per selected account
- Implement account tone profiles: add `tone_prompt` field to accounts.json for each active account
- Build Templates section: templates stored in `templates.json`, accessible from new post modal
- Seed 10 starter templates: PodPal guest promo, SUSA event post, Monday thought leadership, weekly roundup, product launch
- Test with Mic's actual content: generate 5 days of posts from a PodPal episode transcript

**Deliverable:** Mic generates a full week of posts in one session. Review and schedule takes 20 minutes.

---

### Week 2: Full Account Activation + Cross-Platform Formatting

**Goal:** All 10 accounts can receive posts. Platform auto-formats content per platform.

- Audit and reactivate browser sessions for mannmade-x, mannmade-linkedin, podpal-x, susa-x
- Build formatting rules per platform:
  - X: truncate to 280 chars for hook, offer thread mode for longer content
  - LinkedIn: preserve long form, add line breaks, limit to 3 hashtags
  - Instagram: require image attachment, caption under 2,200 chars
  - TikTok: require video or image, short caption
  - Facebook: flexible, cross-post from Instagram or write separately
- Add image upload + basic image requirement enforcement in post modal
- Test posting to all 10 accounts

**Deliverable:** A single post campaign can be distributed to all 10 accounts with appropriate formatting. Singularity SA and PodPal accounts are live.

---

### Week 3: Client Portal Foundation

**Goal:** One external client can log in and see their content calendar.

- Add `/client` route to server.py
- Build simple auth: `clients.json` with email, hashed password, assigned account IDs, branding config
- Build `client.html`: calendar view, queue view, basic analytics (posts this week, platform breakdown)
- Implement approval workflow: posts marked "pending approval" appear in client view with Approve / Request Changes buttons
- Status update triggers notification in main dashboard (unread count badge)
- White-label: client portal reads branding config and applies logo + primary colour

**Deliverable:** Mic can onboard one real client. Client logs in, sees their content, approves or comments on scheduled posts.

---

### Week 4: Analytics Upgrade + Content Idea Bank + Polish

**Goal:** Platform is ready to demo to prospects. Data is visible. UX is tight.

- Pull engagement data from X (likes, reposts, replies) via scraper update to scrape_analytics.py
- Add performance metrics to analytics.html: top 5 posts, best posting time heatmap by platform, topic performance
- Build Content Idea Bank: simple list view in main nav, add idea via text or URL, mark as "used in post"
- Polish: fix any broken account sessions, improve error states in UI, add loading indicators
- Write demo script for first prospect meeting
- Deploy: make platform accessible on local network (not just localhost) so Mic can demo from any device on the same network

**Deliverable:** Platform is demo-ready. Mic walks a prospect through the dashboard, shows their content calendar, and demonstrates AI post generation live.

---

## What Phase 4 Does Not Include

To stay focused, Phase 4 explicitly does not include:
- Ad spend tracking (Phase 5 - needs API access and longer setup)
- Engagement inbox / reply from platform (Phase 5)
- PodPal integration (Phase 5)
- External SaaS launch (Phase 5 - needs security audit first)

The goal for Phase 4 is one thing: turn this into a tool Mic would confidently show a paying client. Everything else can wait.

---

## Closing Note (Zara)

The platform is already doing real work. 114 posts tracked, 54 in the last week. That is not a prototype, that is a working system. Phase 4 is not about proving the concept. It is about multiplying its output and packaging it for revenue.

The 90-day target: 3 paying clients, all 10 accounts active, AI-generated content covering 60% of posts. That is a defensible business line inside Mann Made, and the foundation for a standalone product in Phase 5.

The build is 4 weeks. The payback period on the first client is month one.

---

*Document version 1.0 - March 2026*
*Next review: end of Phase 4 Week 2*
