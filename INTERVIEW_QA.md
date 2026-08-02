# Living Memory — Interview Q&A

---

## SECTION 1: THE PRODUCT

---

**Q: What does Living Memory do? Explain it like I've never heard of it.**

Living Memory is an AI system built for luxury hotels. The core problem it solves is that the best hospitality staff remember personal details about guests — what they drank last time, a trail they mentioned, that they always want the room cool — but that knowledge lives in people's heads. When staff turn over, or when the same guest shows up at a different property, it's gone. A Rosewood guest who had a perfect stay in Hong Kong arrives in Paris to a blank slate.

Living Memory fixes that by automatically capturing guest observations during a stay, storing them, and then surfacing the right details before the guest arrives next time. The AI does the connective tissue work — the humans do the delivery. The guest never knows a system is involved, they just feel genuinely anticipated.

---

**Q: What's the actual user experience? Walk me through it end to end.**

There are two users: guests and staff.

For a guest: before arrival, they get a welcome link. They can have a short voice conversation with the Rosewood Ambassador — a conversational AI — or fill out a quick form. Whatever they share gets stored in their profile. During their stay, nothing changes for them. At checkout, if they opted into Living Memory, their preferences travel with them to every Rosewood property worldwide.

For staff: each morning, the manager dashboard shows today's arrivals. One click triggers the AI pipeline for each guest. Thirty seconds later, the manager has a full arrival dossier — room temperature preference, welcome amenity recommendation, three specific moments to create, a PlaceMaker introduction, and flight status. During the stay, any staff member can capture observations by voice or text on the concierge tablet. The system parses it, extracts action items, and the view updates immediately.

---

**Q: What's a PlaceMaker?**

A PlaceMaker is an in-house expert at the property — could be the executive chef, the sommelier, the wellness director, the art curator. They're not just staff, they're people with deep domain expertise who can create curated, memorable experiences for guests. Living Memory matches each guest's interests to the right PlaceMaker so the introduction feels personal, not random. For example, a guest who mentions a love of California wine gets connected to the sommelier rather than just getting a generic restaurant recommendation.

---

**Q: Who is the target customer?**

Rosewood Hotels and similar luxury chains with multiple properties globally. The system is most valuable at the intersection of high-end hospitality and high guest return rates — where the same guests come back across different properties and the staff's ability to remember them is a genuine competitive differentiator. Rosewood has 33 properties across 21 countries, so the cross-property memory angle is especially relevant.

---

**Q: What's the consent model?**

There are two levels. Standard means the AI uses your information for this stay only — nothing is retained after checkout. Living Memory means your preferences travel across all Rosewood properties, persistently. Guests can also hit "Forget Me Everywhere" to delete all their data. The system is opt-in and transparent — there's a guest data page that shows exactly what's been stored.

---

**Q: Why does this matter for hotels specifically, as opposed to just using a CRM?**

Traditional CRMs require staff to manually enter data — which means it only gets recorded if someone remembers to type it, and only gets surfaced if someone remembers to look. Living Memory captures observations automatically via voice, converts them into structured data using AI, and surfaces the relevant ones proactively before the next arrival. The insight doesn't require anyone to look it up. It also crosses properties automatically, which a standard per-property CRM doesn't do. And crucially, the output goes through a tone filter so it reads like a briefing from a colleague, not a database readout.

---

**Q: What's the Friend Filter?**

Every AI output in the system passes through what we call the Friend Filter before it reaches staff. The idea is simple: would a close colleague who actually knew this guest say this naturally? 

Before the filter, an AI might output: "Guest exhibits 73% rosé preference based on last 5 dinner orders. Dietary flags: pescatarian (confidence: high)."

After the filter: "Samarth usually leans toward something light — a natural rosé or a coastal white would land well. He doesn't eat meat, but he's not fussy about it."

Same information, completely different register. The filter runs on Claude Haiku and is applied to history patterns, wellness notes, and the final synthesized dossier. It's not a cosmetic thing — the clinical readout style can actually make staff feel weird delivering it, so the tone matters for adoption.

---

**Q: What does the arrival plan actually contain?**

It has: a recommended room temperature, a welcome amenity (specific, not generic — like "a glass of Sancerre and the cheese plate" rather than "wine"), three or four specific moments to create during the stay, a suggested itinerary, a PlaceMaker introduction (who to connect them with and why), the live flight status, a jet lag note for staff, and a full warm markdown dossier. All of it is generated by Claude Sonnet based on the guest's actual history.

---

**Q: What problem does the voice interface solve specifically?**

Staff don't want to fill out forms. The observation capture system lets a front desk person say "She mentioned wanting to photograph the valley at golden hour" into their tablet, and that becomes a structured observation with extracted action items immediately. The input modality matches what staff already do — they talk — instead of forcing them into a new workflow.

---

## SECTION 2: SYSTEM ARCHITECTURE

---

**Q: Give me a high-level overview of the technical architecture.**

The backend is Python/FastAPI. The AI layer uses LangGraph for orchestrating multi-agent pipelines and the Anthropic API (Claude) for all LLM calls. The voice layer uses ElevenLabs for both text-to-speech and the two conversational AI agents. The data layer is an in-memory Python graph store backed by JSON, designed with a schema that's Neo4j-compatible when you want to migrate to a real graph database.

The frontend is Next.js with two main views: a staff-facing manager dashboard and concierge tablet, and a guest-facing welcome page and data transparency page.

There are two distinct AI pipelines: the arrival plan pipeline (a DAG with parallel agents) and the Concierge Research Agent (a ReAct loop). Those are architecturally different and serve different purposes.

---

**Q: What is LangGraph and why did you use it?**

LangGraph is a framework for building stateful, graph-structured multi-agent systems. You define agents as nodes in a graph, and edges define how execution flows between them — including parallel execution and conditional branching.

I used it because the arrival plan pipeline has a natural structure that a plain sequential function chain can't express well. Three agents — flight, history, and wellness — have no dependency on each other, so they can and should run concurrently. A fourth agent (PlaceMaker matching) needs the history output before it can run. LangGraph lets me express that topology directly: three parallel edges fan out from the load_context node, all three converge into place_node, then it flows sequentially to the synthesizer.

If I'd used a plain chain, I'd have to run those three agents sequentially and wait for each one, which triples the latency unnecessarily.

---

**Q: Explain the multi-agent pipeline step by step.**

The pipeline has five stages:

1. **load_context** — validates that the guest and stay exist, loads both objects into the shared state. If either is missing, it sets an error flag and all downstream nodes gracefully no-op.

2. **Parallel fan-out** — three agents run concurrently:
   - **flight_node** hits AviationStack to get live flight data and computes a jet lag severity profile based on the origin timezone.
   - **history_node** reads all past observations for this guest across every property, then uses Claude Haiku to extract behavioral patterns, occasions, sensitivities, and standout moments.
   - **wellness_node** reads opt-in wellness signals — in the demo this is mock wearable data — and generates surface-level staff notes.

3. **place_node** — waits for all three parallel nodes to finish (fan-in), then takes the interests extracted by the history agent and matches them against the PlaceMakers at the current property.

4. **synthesize_node** — takes all four agent outputs and passes them to Claude Sonnet with a prompt that produces the full structured arrival plan plus a warm markdown dossier. That output then goes through the Friend Filter.

---

**Q: What's the ArrivalPipelineState and why does it matter?**

It's a TypedDict that defines the schema of the shared state object threaded through every node in the pipeline. Every node reads from it and writes back a partial dict update, which LangGraph merges in. 

The reason it matters: it makes the data flow explicit and verifiable. You can see exactly what fields each node produces and consumes. Each node is independently testable because you can construct a fake state and pass it directly. And if something goes wrong, you can inspect the full state at any point in the execution. It's the difference between a system you can reason about and a chain of function calls where you're guessing what data exists at what point.

---

**Q: What's the difference between the pipeline and the Concierge Research Agent?**

The pipeline is a DAG — it runs on a schedule (morning, for each arriving guest), has a fixed topology, and produces a complete structured document as output. It knows in advance which agents to run and in what order.

The Concierge Research Agent is a ReAct loop — it's for ad-hoc questions from staff throughout the day, things like "Is LH456 on time?", "Who should host this guest?", "What's the weather in Napa right now?" Claude autonomously decides which tools to call, calls them, reasons over the results, and produces an answer. The number and order of tool calls isn't known in advance — Claude figures it out based on the question.

So the pipeline is a scheduled, structured producer. The agent is an interactive, reasoning assistant.

---

**Q: Explain the ReAct loop architecture.**

ReAct stands for Reason + Act. The agent alternates between reasoning and taking actions (tool calls).

In the implementation: the graph has two nodes — agent_node and tool_node. agent_node calls Claude with the current conversation history and the tool definitions. If Claude decides to call a tool, it returns a "tool_use" stop reason and the content includes tool call blocks. The router sends execution to tool_node. tool_node executes the tools, appends the results as a user message, and loops back to agent_node. Claude then reasons over the tool results and either calls more tools or produces a final answer with an "end_turn" stop reason. There's a `_MAX_STEPS = 6` safety cap that forces a final answer if the loop runs too long.

---

**Q: What is MCP and how does it relate to your tool definitions?**

MCP stands for Model Context Protocol — it's a standard for how tools are defined and exposed to AI models. The format is: a name, a description, and an `input_schema` that's standard JSON Schema with properties and required fields.

I used MCP-format tool definitions for the three tools in the Concierge Research Agent — `get_weather`, `get_flight_status`, and `find_placemaker`. This is the same schema format used by the Anthropic tool-use API. So the tools are both MCP-compatible and natively usable by Claude. If you wanted to expose these tools through an actual MCP server for other agents to consume, the definitions are already in the right format.

---

**Q: Walk me through the three MCP tools.**

**get_weather** — calls `wttr.in`, a free weather API, for any city. Returns temperature in both Celsius and Fahrenheit, humidity, wind speed, and a description. Staff use it for arrival planning, activity recommendations, what to suggest a guest pack.

**get_flight_status** — takes an IATA flight number (like LH456), hits AviationStack for live status, and returns the airline, route, scheduled vs. estimated arrival, gate, terminal, delay info, and a jet lag severity note. The jet lag note is computed by looking up the origin airport's UTC offset from a lookup table and comparing it to the property's timezone (PDT, UTC-7). Falls back to a demo flight if no API key is configured.

**find_placemaker** — this one is different from the other two. Instead of hitting an external API, it queries Living Memory's own internal knowledge graph. It takes a free-text description of a guest's interests, tokenizes it, and scores each PlaceMaker at the property by keyword overlap against their role, bio, offerings, and ideal guest profiles. Returns the top three matches with their signature offerings. The fact that one tool reasons over internal data and two hit external APIs is architecturally intentional — it shows the agent can bridge both.

---

**Q: How does the jet lag calculation work?**

Each origin airport IATA code maps to a UTC offset in a hardcoded lookup table — FRA is +2, SFO is -7, NRT is +9, etc. The property is at PDT (UTC-7). The calculation takes the absolute difference between origin offset and destination offset. If the difference is under 3 hours, severity is "minimal." 3-5 hours is "moderate." 5-8 hours is "significant." Over 8 hours is "severe." The staff note is then phrased appropriately — for a 9-hour gap like Frankfurt to SFO, you get "Likely experiencing significant jet lag. Consider a lighter schedule for day one, offer hydration, and avoid scheduling anything mentally demanding in the first few hours."

---

**Q: Explain the data model.**

There are six core entities: Guest, Stay, Observation, PlaceMaker, Property, and ArrivalPlan. All defined as Pydantic models.

A Guest has a consent level, a list of stay IDs, a preferences dict, and a `property_aliases` field for cross-property identity resolution. A Stay belongs to one guest and one property, has check-in/out dates, room details, and a list of observation IDs. Observations are the atomic unit — a single piece of staff input with raw text, structured tags, sentiment, and a source (staff voice, staff text, welcome call, PMS). PlaceMakers belong to a property and have offerings, availability windows, and ideal guest profiles. ArrivalPlan is the output — it stores the synthesized dossier and structured fields.

The storage layer is an in-memory dict with JSON persistence, and the schema is Neo4j-compatible by design, so migrating to a real graph database is a lift-and-shift of the data layer, not a rewrite of the models.

---

**Q: How does cross-property identity resolution work?**

Each guest has a `property_aliases` dict that maps property IDs to local guest IDs from that property's PMS. There's an `identity.py` module with fuzzy matching — it compares name similarity, email, phone, and nationality across guest records from different properties to find likely duplicates. When a match is found, the profiles can be merged. In production you'd route this through a review queue before auto-merging, but the matching logic is in place.

---

**Q: How does the observation capture pipeline work?**

Staff dictate or type a note: "She mentioned wanting to photograph the valley at golden hour." The `parse_observation` function sends that raw text to Claude Haiku with a structured extraction prompt. Claude returns: the key insight as a normalized sentence, a list of tags (e.g., "photography", "outdoor", "golden-hour"), a sentiment (positive/neutral/negative), and a list of action items ("Note in dossier: suggest sunrise hike or golden hour on the terrace"). That structured data gets stored in the graph as an Observation object linked to the guest and stay.

---

**Q: How does the ElevenLabs integration work?**

There are two ElevenLabs conversational AI agents. The Welcome Ambassador handles the pre-arrival voice call — it has a system prompt that introduces Rosewood, asks about the guest's preferences and occasions, and wraps up warmly. The In-Stay Concierge is available during the stay with full knowledge of the property and PlaceMakers for live voice requests.

The backend has a `get_signed_url` endpoint that returns a temporary signed URL from ElevenLabs, which the frontend uses to establish a WebSocket connection for the voice session. When the call ends, ElevenLabs sends a post-call webhook with the transcript, which gets processed by the `welcome_summarizer` agent (Claude Haiku) to extract structured preferences that merge into the guest profile.

---

## SECTION 3: TECHNICAL DEEP-DIVES

---

**Q: How does LangGraph actually handle parallel execution?**

When multiple edges point to the same downstream node (fan-in), LangGraph automatically runs all upstream nodes concurrently and waits for all of them to complete before triggering the downstream node. In the pipeline, load_context has three outgoing edges to flight_node, history_node, and wellness_node. All three have an incoming edge to place_node. LangGraph uses Python's async machinery under the hood to run those three concurrently. Each node returns a partial dict update; LangGraph merges all three updates into the shared state before place_node runs.

---

**Q: What's an Annotated list and why does the MCP agent use one?**

In the MCP agent's state, the messages field is defined as `Annotated[list, operator.add]`. This tells LangGraph to merge updates to that field using the `operator.add` function — which for lists means concatenation (append), not replacement. 

Without this, every time a node returned `{"messages": [...new messages...]}`, LangGraph would replace the entire messages list. With `operator.add`, it appends the new messages to the existing list. This is critical for the ReAct loop: each round of agent_node and tool_node adds to the conversation history, and Claude needs to see the full history on every call so it can reason over accumulated tool results.

---

**Q: How do you prevent the ReAct loop from running forever?**

Two mechanisms. First, `_MAX_STEPS = 6` — the agent_node checks the current step count at the top. If it's at or beyond the limit, instead of calling Claude with tools available, it calls Claude without tools and forces a final answer. Second, the routing function `_route_after_agent` only sends execution to tool_node if the last assistant message contains a tool_use block. If Claude produces an end_turn response (just text, no tool calls), execution goes to END. So the loop terminates either when Claude decides to stop using tools, or when the step cap hits.

---

**Q: How does the tool dispatch work in the MCP agent?**

There's a `_TOOL_REGISTRY` dict that maps tool names to lambda functions. When tool_node processes a response, it iterates over all tool_use blocks in the last assistant message, looks up each tool name in the registry, calls the lambda with the input dict, and collects the results as tool_result blocks. The tool_result blocks are assembled into a single user message and appended to the conversation. This design means adding a new tool is a two-step operation: add the tool definition to `MCP_TOOLS`, add the callable to `_TOOL_REGISTRY`.

---

**Q: Why does the PlaceMaker search use keyword overlap instead of embedding similarity?**

A few reasons. First, the PlaceMaker dataset is small — a handful of experts per property — so the overhead of generating and storing embeddings isn't justified. Second, keyword overlap is transparent and debuggable: you can see exactly which terms matched and why. Third, the queries tend to use concrete nouns ("wine", "wellness", "chef") that overlap well with the PlaceMaker descriptions. For a larger dataset or more nuanced matching, you'd move to embeddings, but at this scale keyword overlap is fast, cheap, and interpretable.

---

**Q: What models does the system use and why those choices?**

There are two models in use:
- **Claude Haiku** (`claude-haiku-4-5`) — used for the fast_model tasks: Friend Filter rewrites, observation parsing, history extraction, and the MCP agent's ReAct loop. It's fast and cheap, which matters for high-frequency operations and the real-time observation capture flow.
- **Claude Sonnet** (`claude-sonnet-4-5`) — used for the orchestrator_model task: the synthesizer that writes the full arrival plan and dossier. This is the one place where output quality is most visible to staff, so it's worth the extra cost and latency.

Both are configurable in `config.py`.

---

**Q: How does the caching work for flight data?**

The flight module writes results to `data/flight_cache.json` with a timestamp. When a flight is requested, it first checks the cache. If the cached entry is less than 120 seconds old (the `_CACHE_TTL`), it returns the cached result without hitting AviationStack. If it's stale or missing, it hits the API and updates the cache. On API failure, it falls back to stale cache if available, and if there's no cache entry at all, it returns a demo flight (the FRA→SFO Lufthansa flight used for the demo guest). This means the system degrades gracefully at every level: fresh data → stale cache → demo data.

---

**Q: How is the app structured on the backend? What does the FastAPI layer look like?**

The FastAPI app has routes organized by concern:
- Guest management: create guest, get guest, update consent
- Stay management: create stay, get stay
- Observations: capture observation (text or voice), get observations for a stay
- Arrivals: trigger plan generation, get plan, stream plan audio
- Agent: POST /agent/query (run the MCP agent), GET /agent/tools (list tool catalogue)
- Voice: get signed URL for ElevenLabs, process transcript
- PMS webhook: receive reservation from a property management system
- Identity: trigger cross-property duplicate detection

There's also a seed_data startup handler that loads property data, PlaceMakers, and synthetic guest data from JSON files when the server starts.

---

## SECTION 4: THE EVAL SUITE

---

**Q: Why did you build an eval suite for an AI agent?**

Because pass/fail tests aren't sufficient for evaluating language model behavior. A unit test can tell you whether the right tool was called, but it can't tell you whether the final answer was actually useful, whether the agent was efficient, or whether it fabricated information. Standard assertions are binary — they catch regressions but they don't measure quality.

The eval suite has two layers specifically to address this. Layer one is the standard pytest suite with binary assertions. Layer two is a rubric-based LLM-as-judge that scores the agent on dimensions like factuality and step efficiency, and reports mean scores per failure category. That second layer surfaces the kinds of failures — wrong tone, fabricated details, unnecessary tool calls — that a binary test would pass.

---

**Q: Walk me through the test structure.**

There are two test files.

`test_mcp_agent.py` has 16 unit tests (no LLM, no API keys, run in about 3 seconds) and 11 integration tests (require ANTHROPIC_API_KEY). The unit tests call each tool function directly and check the output structure. The integration tests run the full ReAct agent on eval cases from `eval/cases.py` and assert: the agent produced an answer, no error occurred, the expected tools were called, expected keywords appear in the answer, and the agent used at most 6 steps.

`test_rubric_scorer.py` has 39 unit tests for the scorer itself, using a mocked judge so no API calls are needed. These test JSON parsing edge cases, weight validation, slice aggregation logic, and markdown report generation.

---

**Q: What are the eval cases testing and how are they organized?**

There are 9 eval cases organized into 6 failure-mode slices:

- **single-tool-external** — one external API call, e.g., weather lookup or basic flight status. Tests that the agent makes the right call and returns a useful answer.
- **single-tool-internal** — one internal graph query, e.g., PlaceMaker search for a wine enthusiast or a wellness match for a long-haul arrival.
- **multi-tool** — chained reasoning, e.g., check a flight AND find the right PlaceMaker based on the guest's stated interests. Tests that Claude calls both tools and synthesizes a coherent response.
- **no-tool** — a question the agent should answer directly without calling any tools, like "What's the capital of France?" Tests that the agent doesn't over-tool-call.
- **ambiguous-query** — a vague request like "I have a guest arriving, what should I prepare?" Tests that the agent asks for clarification or responds helpfully rather than guessing badly.
- **degraded-api** — a tool that will return an error, like a nonsense location for weather. Tests that the agent reports the error gracefully rather than fabricating an answer.

---

**Q: How does the LLM-as-judge work?**

After the agent runs on each eval case, the rubric scorer builds a detailed prompt for the judge that includes: the case ID, the slice category, the query, what tools were expected, what keywords were expected, how many steps the agent took, the full tool call log with inputs and outputs, and the final answer. It then asks Claude (the judge model — defaults to Sonnet) to score the agent on four dimensions and return a JSON object.

The JSON has one entry per dimension: a score from 0 to 1 and a one-sentence reasoning. The scorer parses that JSON, handles edge cases like code fences, missing dimensions, and out-of-range scores, computes the weighted total, and stores the result as a `CaseScore` object.

---

**Q: What are the four rubric dimensions and how are they weighted?**

- **tool_selection** (weight 0.30) — Did the agent call the right tools? Penalizes wrong tools, missing tools, and unnecessary tool calls. If no tool was needed, it checks that the agent correctly answered directly.
- **factuality** (weight 0.40) — Is the answer grounded in the tool outputs? Penalizes fabrication or contradictions of what the tools actually returned. This is the highest-weight dimension because making up information is the most harmful failure mode.
- **step_efficiency** (weight 0.20) — Did the agent finish in a reasonable number of steps? Penalizes redundant or unnecessary tool calls.
- **loop_safety** (weight 0.10) — Did the agent stay bounded? Scores 1.0 for 4 steps or fewer, 0.5 for 5-6, 0.0 for apparent looping or hitting the max step cap.

The weights sum to 1.0, and the final composite score is the weighted sum.

---

**Q: Can you give an example of what the rubric caught that a standard test wouldn't?**

Yes. On the `degraded_api_bad_location` case — where the query is "What's the weather in xkqzpwrt12345 right now?" — a standard test would pass as long as the agent called get_weather and said something about an error. But the rubric found that the agent was short-circuiting: it recognized the location as nonsense and refused to call the tool at all, instead just saying "that doesn't look like a real location." That's a tool_selection score of 0.0 (tool was expected but not called), a factuality score of 0.8 (the reasoning was correct but not grounded in tool output), and a weighted total of around 0.30. The binary test would have failed too on the tool assertion, but the rubric tells you *why* it failed and *how bad* it was — which helps you decide how to fix it.

---

**Q: What does the markdown report look like?**

The report has four sections: a header with overall weighted score, worst-performing cases surfaced at the top (so you see failures first, not last), an overall per-dimension table showing mean scores across all cases, and a per-slice breakdown table showing which categories perform poorly. There's also a full per-case appendix. The worst-cases-first ordering is intentional — in a real eval loop, you're looking for regressions, so you want to see the bottom of the distribution immediately.

---

**Q: How do you run the eval suite?**

Unit tests only (no API keys needed, runs in ~3 seconds):
```
cd backend && pytest tests/test_mcp_agent.py -v -m "not integration"
```

All tests including integration:
```
pytest tests/test_mcp_agent.py -v -m integration -s
```

Full rubric eval with markdown report output:
```
python -m eval.run_eval
```

Single slice only:
```
python -m eval.run_eval --slice degraded-api
```

Using a faster/cheaper judge model:
```
python -m eval.run_eval --judge-model claude-haiku-4-5
```

---

**Q: Why is EVAL_CASES defined in a separate file instead of in the test file?**

Because both the pytest suite and the rubric CLI runner need the same cases. If it was defined in the test file, the CLI runner would have to import from a test file, which is a weird dependency. By putting it in `eval/cases.py`, both consumers import from the same canonical source. If you add a new case, it automatically shows up in both the pytest parametrize and the rubric run. It also makes the cases independently readable — someone can look at `cases.py` and understand what the agent is expected to do without reading the test harness code.

---

## SECTION 5: TRADE-OFFS AND DESIGN DECISIONS

---

**Q: What were the biggest technical trade-offs you made?**

The biggest one was storage. I used an in-memory Python dict with JSON persistence rather than a real database. This is fine for a hackathon demo — it boots instantly, needs zero infrastructure, and the Pydantic models are schema-identical to what you'd use with Neo4j. But it means no concurrent writes, no querying beyond Python list comprehensions, and data resets on crash. The right production move is Neo4j for the graph relationships and Postgres for the transactional data, but the abstraction layer is designed to make that migration surgical.

The second trade-off was using keyword overlap for PlaceMaker matching instead of semantic embeddings. Keyword overlap is transparent and fast, but it'll miss synonyms — a guest who says "viticulture" won't match "wine." For a production system with more diverse queries, you'd want vector similarity. At hackathon scale with a handful of PlaceMakers and straightforward queries, it works well.

---

**Q: Why LangGraph instead of just writing the agents as plain Python functions?**

Three reasons. First, parallel execution — I can't do the fan-out/fan-in pattern cleanly with plain functions without writing threading or async code myself. LangGraph handles the concurrency. Second, typed shared state — instead of passing a growing dict of kwargs through every function, every node reads and writes to a single typed state object, which makes the data flow explicit and debuggable. Third, conditional routing hooks — the graph is designed for conditional branching (Living Memory guests get a richer prompt, guests who haven't opted into wellness skip that node), and LangGraph's conditional edge API makes that easy to add without restructuring the code.

---

**Q: What would you change if you had more time?**

A few things. First, replace the JSON file store with a real database — Neo4j for the graph and Postgres for the rest. Second, move from keyword matching to embedding-based PlaceMaker search for better semantic coverage. Third, wire up real conditional routing in the LangGraph pipeline — a Living Memory guest should trigger a richer synthesizer prompt that explicitly weaves in cross-property patterns, while a Standard guest gets a clean current-stay-only plan. Fourth, close the loop on PlaceMaker availability and booking — right now the system recommends but doesn't connect to scheduling. The last mile between "recommend Natalie for a recovery session" and "Natalie has a 10am opening Tuesday" is the most valuable piece that's missing.

---

**Q: How would you scale this?**

The pipeline is the thing that needs to scale. For a large property with many arrivals, you'd want to: run the LangGraph pipeline asynchronously in a task queue (Celery or similar) rather than blocking an API request, cache flight data aggressively since multiple staff may query the same flight, and shard the graph store by property so each property's data is isolated. The Friend Filter and observation parsing are stateless Claude calls so they scale horizontally without changes. The ElevenLabs voice connections are per-session and handled by ElevenLabs' infrastructure.

---

**Q: What security and privacy considerations did you account for?**

The consent model is the main one — data is partitioned by consent level and a "Forget Me Everywhere" deletion flows through all stores. The friend filter is partly a privacy mechanism too — it ensures the AI doesn't expose clinical-sounding readouts about a guest to staff who don't have medical training. API keys are in environment variables, not in code. The manager dashboard has a password gate (demo-level, not production-level). For production you'd add proper auth (OAuth/JWT), audit logging of who accessed which guest profile, and data residency controls so European guest data stays in EU infrastructure.

---

## SECTION 6: FOLLOW-UP / CURVEBALL QUESTIONS

---

**Q: Why Claude specifically? Why not GPT-4 or Gemini?**

A few reasons. The tool-use API is well-specified and the JSON output is reliable, which matters a lot for the rubric scorer and the synthesizer where I'm parsing structured output. Claude Haiku is genuinely fast and cheap for the high-frequency operations. And the Friend Filter requires a model that's naturally good at tone rewriting — Claude's outputs in that register are warm without being saccharine. That said, the models are all configured in `config.py` as string fields, so swapping is a one-line change.

---

**Q: How would you detect if the AI is hallucinating something about a guest?**

Two ways, currently. First, the rubric scorer's factuality dimension — the judge explicitly checks whether the answer is grounded in the tool outputs and penalizes claims that aren't. Second, the observation parser returns structured data including the raw text, so you can always trace a claim back to its source observation. In production you'd want a confidence signal on the synthesis — probably a separate Claude call that reads the final dossier and the source observations and flags anything that can't be directly traced.

---

**Q: What happens if AviationStack is down?**

Three-level degradation: fresh API data → stale cached data (any result from a previous successful call, regardless of TTL) → demo flight data. The system never returns an error to the pipeline — it always has something to show. The staff note in the plan would indicate the data might be stale if you wanted to add that transparency, but the pipeline doesn't break.

---

**Q: Could the Concierge Research Agent call the arrival plan pipeline as a tool?**

Not currently, but architecturally yes. You could define a `generate_arrival_plan` tool that takes a guest ID and triggers the pipeline, and add it to the MCP_TOOLS list and _TOOL_REGISTRY. The agent could then answer questions like "run the arrival plan for guest 123 and tell me the jet lag note" in a single turn. The existing design keeps them separate because they have different latency profiles — the pipeline takes ~10 seconds while the agent is designed for sub-3-second queries — but composing them is a reasonable next step.

---

**Q: The Friend Filter runs on Claude Haiku — what if it rewrites something incorrectly?**

It's a known risk. The filter is designed to change tone, not content, and the prompt is explicit about that. But a model could drop a detail or paraphrase something in a way that loses precision. Two mitigations: first, the raw dossier is also stored in the ArrivalPlan alongside the filtered version, so staff could in principle see the original. Second, the filter is applied after the synthesizer, which means the structured fields (room temperature, welcome amenity, moments) are extracted before filtering and stored as structured data — the filter only rewrites the prose dossier. So even a bad rewrite doesn't corrupt the structured fields that drive actual actions.

---

**Q: What would a production deployment look like?**

Backend: FastAPI on a container (Docker), orchestrated on Kubernetes or ECS. Task queue (Celery + Redis) for async pipeline runs. Neo4j Cloud for the graph store, Postgres for relational data. Secret management via AWS Secrets Manager or similar — no env files in production. CDN for the frontend (Vercel or CloudFront). ElevenLabs webhook requires a public URL, so that's a real endpoint (not ngrok). Property data would be loaded from an admin interface rather than JSON files. Auth would be proper OAuth with staff roles.

---

**Q: If this were a real product, how would you price it?**

Per-property SaaS subscription makes the most sense, with pricing tied to the number of arrivals per month since that's the main cost driver (each arrival triggers 4-5 Claude API calls). A mid-sized Rosewood property with 30 arrivals a day would cost maybe $5-10/day in API costs at current Claude pricing, which is trivially small compared to the ADR (average daily rate) of a luxury hotel room. You'd probably price at something like $2,000-5,000/month per property, with a cross-property Living Memory premium for chains.

---

**Q: Is there anything in the project you'd do completely differently?**

The observation parsing pipeline I'd redesign. Currently it's a single Claude call that does extraction, tagging, and action item generation all at once. In production, I'd split that into stages with validation between them — extract first, then verify the tags are consistent with the raw text, then generate action items. The single-call approach is fast and good enough for a demo, but in a real system you'd want more control over each step so you can tune and test them independently.

Also, the identity resolution is currently a one-time batch operation. In production it should run automatically when a new guest is created — check for duplicates, surface candidates for review, and merge with human approval. The algorithm is there, the workflow integration isn't.
