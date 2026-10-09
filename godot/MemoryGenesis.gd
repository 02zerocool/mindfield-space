## MemoryGenesis.gd — Autonomous memory geometry engine (Mindfield-Space)
##
## Configured for space mission domains:
##   telemetry · procedures · fmea · propulsion · astrodynamics
##   life_support · comms · science · regulations · planetary
##
## Every TICK_S seconds queries a domain lean_api for the next rotating thought.
## The result manifests as a "thought burst" — BURST_COUNT glowing particles
## erupting from the corresponding domain cluster, expanding and fading over BURST_TTL.
##
## Setup:
##   1. Add as child Node3D in your scene
##   2. Set LEAN_URL to your main lean_api address (or per-domain URLs in DOMAIN_URLS)
##   3. Set enabled = true to activate
##
## Shader: requires res://shaders/star_point.gdshader (or substitute your own)

extends Node3D

const LEAN_URL    := "http://127.0.0.1:8018"  # main lean_api
const TICK_S      := 8.0
const BURST_COUNT := 80
const BURST_TTL   := 5.0

var enabled : bool = false

# ── Per-domain lean_api URLs (optional) ───────────────────────────────────────
# If a domain runs its own lean_api on a separate port, route queries there.
# Leave as "" to use the main LEAN_URL for all domains.
const DOMAIN_URLS := {
	"telemetry":    "http://127.0.0.1:18001",
	"procedures":   "http://127.0.0.1:18002",
	"fmea":         "http://127.0.0.1:18003",
	"propulsion":   "http://127.0.0.1:18004",
	"astrodynamics":"http://127.0.0.1:18005",
	"life_support": "http://127.0.0.1:18006",
	"comms":        "http://127.0.0.1:18007",
	"science":      "http://127.0.0.1:18008",
	"regulations":  "http://127.0.0.1:18009",
	"planetary":    "http://127.0.0.1:18010",
}

# ── Domain positions and colours ───────────────────────────────────────────────
const DOMAINS := {
	"telemetry":    {"pos": Vector3(-8,  2, -5),  "col": Color(0.2, 0.8, 1.0)},   # cyan
	"procedures":   {"pos": Vector3( 6,  3, -7),  "col": Color(0.9, 0.9, 1.0)},   # white
	"fmea":         {"pos": Vector3( 0,  8,  2),  "col": Color(1.0, 0.3, 0.2)},   # red
	"propulsion":   {"pos": Vector3(-5, -3,  8),  "col": Color(1.0, 0.6, 0.2)},   # orange
	"astrodynamics":{"pos": Vector3( 9, -2,  4),  "col": Color(0.5, 0.3, 1.0)},   # violet
	"life_support": {"pos": Vector3(-7,  5,  3),  "col": Color(0.3, 0.9, 0.4)},   # green
	"comms":        {"pos": Vector3( 4, -6, -6),  "col": Color(0.2, 0.6, 1.0)},   # sky blue
	"science":      {"pos": Vector3(-3, -7, -4),  "col": Color(0.9, 0.4, 0.8)},   # magenta
	"regulations":  {"pos": Vector3( 7,  4,  5),  "col": Color(0.85,0.85,0.6)},   # pale gold
	"planetary":    {"pos": Vector3(-6, -5, -8),  "col": Color(0.7, 0.5, 0.3)},   # Mars brown
}

# ── Thought sequence ───────────────────────────────────────────────────────────
const THOUGHT_SEQUENCE := [
	{"domain": "telemetry",     "query": "sensor anomaly out of limit thermal"},
	{"domain": "telemetry",     "query": "power system voltage current fault"},
	{"domain": "procedures",    "query": "crew egress procedure emergency contingency"},
	{"domain": "procedures",    "query": "EVA suit donning checklist depressurisation"},
	{"domain": "fmea",          "query": "single point failure critical system redundancy"},
	{"domain": "fmea",          "query": "anomaly root cause investigation lessons learned"},
	{"domain": "propulsion",    "query": "thruster specific impulse burn sequence abort"},
	{"domain": "propulsion",    "query": "propellant loading oxidizer fuel ratio"},
	{"domain": "astrodynamics", "query": "orbital insertion periapsis apoapsis maneuver"},
	{"domain": "astrodynamics", "query": "debris collision avoidance proximity operations"},
	{"domain": "life_support",  "query": "CO2 removal water recovery oxygen generation"},
	{"domain": "life_support",  "query": "cabin pressure humidity environmental control"},
	{"domain": "comms",         "query": "link budget deep space network contact schedule"},
	{"domain": "comms",         "query": "high gain antenna acquisition signal loss"},
	{"domain": "science",       "query": "instrument calibration measurement requirement"},
	{"domain": "science",       "query": "spectral resolution detection limit observation"},
	{"domain": "regulations",   "query": "NASA-STD safety requirement verification"},
	{"domain": "regulations",   "query": "planetary protection human rating certification"},
	{"domain": "planetary",     "query": "Mars regolith atmosphere dust storm composition"},
	{"domain": "planetary",     "query": "Europa ocean astrobiology biosignature detection"},
]

var _tick_acc      : float  = TICK_S
var _current_domain: String = ""
var _http          : HTTPRequest = null
var _bursts        : Array  = []
var _shader        : Shader = null
var _rng           := RandomNumberGenerator.new()


func _ready() -> void:
	name = "MemoryGenesis"
	_rng.randomize()
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_result)
	_shader = load("res://shaders/star_point.gdshader")
	if _shader == null:
		push_warning("[MemoryGenesis] star_point.gdshader not found — using fallback material")
	print("[MemoryGenesis] online — %d thoughts  %.0fs interval  %d burst  TTL %.0fs  shader=%s" % [
		THOUGHT_SEQUENCE.size(), TICK_S, BURST_COUNT, BURST_TTL,
		"custom" if _shader else "fallback"])


func _process(delta: float) -> void:
	if enabled:
		_tick_acc += delta
		if _tick_acc >= TICK_S:
			_tick_acc = 0.0
			_fire_thought()

	for i in range(_bursts.size() - 1, -1, -1):
		var b : Dictionary = _bursts[i]
		b.elapsed += delta
		var t : float = clampf(b.elapsed / BURST_TTL, 0.0, 1.0)

		if t >= 1.0:
			if is_instance_valid(b.mmi):
				b.mmi.queue_free()
			_bursts.remove_at(i)
			continue

		if not is_instance_valid(b.mmi):
			_bursts.remove_at(i)
			continue

		var expansion : float = 1.0 + t * 2.5
		var alpha     : float = pow(1.0 - t, 1.5)
		b.mmi.scale = Vector3(expansion, expansion, expansion)
		_set_burst_alpha(b.mmi.multimesh, alpha)


func _fire_thought() -> void:
	var status := _http.get_http_client_status()
	if status != HTTPClient.STATUS_DISCONNECTED and \
	   status != HTTPClient.STATUS_CONNECTION_ERROR:
		return

	var idx     : int    = _rng.randi_range(0, THOUGHT_SEQUENCE.size() - 1)
	var thought : Dictionary = THOUGHT_SEQUENCE[idx]
	_current_domain = thought.domain

	# Route to domain-specific lean_api if configured
	var url : String = DOMAIN_URLS.get(_current_domain, LEAN_URL)
	var body := JSON.stringify({"query": thought.query, "k": 20})
	var headers := PackedStringArray(["Content-Type: application/json"])
	var err := _http.request(url + "/search", headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		push_error("[MemoryGenesis] HTTP request failed: %d" % err)


func _on_result(result: int, code: int, _headers: PackedStringArray,
		body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		return

	var json = JSON.parse_string(body.get_string_from_utf8())
	if json == null or not json is Dictionary:
		return

	var results : Array = json.get("results", [])
	var snippet : String = ""
	if results.size() > 0:
		var pick : int = _rng.randi_range(0, min(results.size() - 1, 14))
		snippet = str(results[pick].get("content", "")).left(80)

	if not DOMAINS.has(_current_domain):
		return

	var d : Dictionary = DOMAINS[_current_domain]
	_spawn_burst(d.pos, d.col, _current_domain, snippet)


func _spawn_burst(centre: Vector3, col: Color, domain: String, snippet: String) -> void:
	var mm := MultiMesh.new()
	mm.use_colors       = true
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.instance_count   = BURST_COUNT

	var rng := RandomNumberGenerator.new()
	var buf := PackedFloat32Array()
	buf.resize(BURST_COUNT * 16)
	buf.fill(0.0)

	for i in BURST_COUNT:
		var theta : float = rng.randf() * TAU
		var phi   : float = rng.randf() * PI
		var r     : float = absf(rng.randfn(0.0, 0.6))
		var lx    : float = r * sin(phi) * cos(theta)
		var ly    : float = r * sin(phi) * sin(theta)
		var lz    : float = r * cos(phi)
		var sz    : float = 0.8 + rng.randf() * 1.8

		var b : int = i * 16
		buf[b + 0]  = sz;  buf[b + 5]  = sz;  buf[b + 10] = sz
		buf[b + 3]  = lx;  buf[b + 7]  = ly;  buf[b + 11] = lz
		buf[b + 12] = col.r;  buf[b + 13] = col.g
		buf[b + 14] = col.b;  buf[b + 15] = 1.0

	mm.buffer = buf

	var quad := QuadMesh.new()
	quad.size = Vector2(1.0, 1.0)
	if _shader:
		var mat := ShaderMaterial.new()
		mat.shader = _shader
		mat.set_shader_parameter("base_pixels", 7.0)
		quad.material = mat
	else:
		var mat := StandardMaterial3D.new()
		mat.shading_mode     = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.billboard_mode   = BaseMaterial3D.BILLBOARD_ENABLED
		mat.vertex_color_use_as_albedo = true
		mat.transparency     = BaseMaterial3D.TRANSPARENCY_ALPHA
		quad.material = mat
	mm.mesh = quad

	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh   = mm
	mmi.position    = centre
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi.custom_aabb = AABB(Vector3(-20, -20, -20), Vector3(40, 40, 40))
	add_child(mmi)

	_bursts.append({"mmi": mmi, "elapsed": 0.0})
	print("[MemoryGenesis] THOUGHT [%s] -> '%s...' @%.0f,%.0f,%.0f" % [
		domain, snippet, centre.x, centre.y, centre.z])


func _set_burst_alpha(mm: MultiMesh, alpha: float) -> void:
	var buf := mm.buffer
	if buf.is_empty():
		return
	var n : int = buf.size() / 16
	for i in n:
		buf[i * 16 + 15] = alpha
	mm.buffer = buf
