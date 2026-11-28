import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const corsHeaders = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
};

function response(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), { status, headers: corsHeaders });
}

function env(name: string): string {
  return Deno.env.get(name) ?? "";
}

async function supabaseRequest(path: string, method = "GET", body?: unknown) {
  const base = env("SUPABASE_URL");
  const key = env("SUPABASE_SERVICE_ROLE_KEY");
  if (!base || !key) throw new Error("Server database credentials are not configured.");
  const headers: Record<string, string> = {
    "apikey": key,
    "Authorization": `Bearer ${key}`,
    "Content-Type": "application/json",
  };
  const result = await fetch(`${base}/rest/v1/${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await result.text();
  if (!result.ok) throw new Error(`Database request failed (${result.status}): ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

function constantTimeEqual(left: string, right: string): boolean {
  const a = new TextEncoder().encode(left);
  const b = new TextEncoder().encode(right);
  let difference = a.length ^ b.length;
  const length = Math.max(a.length, b.length);
  for (let i = 0; i < length; i++) {
    difference |= (a[i] ?? 0) ^ (b[i] ?? 0);
  }
  return difference === 0;
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response(405, { error: "Method not allowed." });

  const ingestKey = env("V9_INGEST_KEY");
  if (!ingestKey) return response(503, { error: "Ingestion is not configured yet." });

  const suppliedKey = req.headers.get("x-v9-ingest-key") ?? "";
  if (!constantTimeEqual(suppliedKey, ingestKey)) {
    return response(401, { error: "Unauthorized." });
  }

  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > 1_000_000) {
    return response(413, { error: "Payload too large." });
  }

  // Enforce the payload limit while streaming; Content-Length can be absent.
  let payload: Record<string, unknown>;
  try {
    if (!req.body) throw new Error("Missing request body.");
    const reader = req.body.getReader();
    const chunks: Uint8Array[] = [];
    let totalBytes = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalBytes += value.byteLength;
      if (totalBytes > 1_000_000) {
        await reader.cancel();
        return response(413, { error: "Payload too large." });
      }
      chunks.push(value);
    }

    const bytes = new Uint8Array(totalBytes);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("JSON payload must be an object.");
    }
    payload = parsed as Record<string, unknown>;
  } catch {
    return response(400, { error: "Invalid JSON object." });
  }

  const v9 = payload.v9_report as Record<string, unknown> | undefined;
  const risk = payload.risk_report as Record<string, unknown> | undefined;
  if (!v9 || !risk || v9.mode !== "READ ONLY" || risk.mode !== "READ ONLY") {
    return response(400, { error: "Both reports must be present and explicitly READ ONLY." });
  }

  const rawSignals = v9.results;
  if (!Array.isArray(rawSignals) || rawSignals.length > 100) {
    return response(400, { error: "Invalid signal list." });
  }
  if (!Array.isArray(risk.flags) || !risk.metrics || typeof risk.metrics !== "object") {
    return response(400, { error: "Invalid risk report." });
  }

  try {
    let insertedSignals = 0;
    let duplicateSignals = 0;

    for (const item of rawSignals) {
      if (!item || typeof item !== "object") continue;
      const signal = item as Record<string, unknown>;
      const symbol = String(signal.symbol ?? "");
      const entryTime = String(signal.entry_time_ms ?? "");
      const score = Number(signal.score);
      const price = Number(signal.price);
      if (!/^[A-Z0-9]{3,30}$/.test(symbol) ||
          !/^\d{10,16}$/.test(entryTime) ||
          !Number.isFinite(score) || score < 0 || score > 100 ||
          !Number.isFinite(price) || price <= 0 ||
          signal.direction !== "BUY") {
        continue;
      }

      const dedupeFilter = new URLSearchParams({
        select: "id",
        symbol: `eq.${symbol}`,
        market: "eq.crypto",
        timeframe: "eq.15m",
        "signal_payload->>entry_time_ms": `eq.${entryTime}`,
        limit: "1",
      });
      const existing = await supabaseRequest(`market_signals?${dedupeFilter.toString()}`);
      if (Array.isArray(existing) && existing.length > 0) {
        duplicateSignals++;
        continue;
      }

      const rationale = String(signal.status ?? "V9 read-only screening result").slice(0, 1000);
      await supabaseRequest("market_signals", "POST", [{
        symbol,
        market: "crypto",
        timeframe: "15m",
        direction: "BUY",
        confidence: score,
        strategy: String(v9.version ?? "V9").slice(0, 100),
        rationale,
        signal_payload: {
          ...signal,
          entry_time_ms: entryTime,
          source: "V9_READ_ONLY_ENGINE",
          mode: "READ ONLY",
          price,
        },
      }]);
      insertedSignals++;
    }

    const owners = await supabaseRequest(
      `user_roles?select=user_id&role=eq.owner`,
    );
    if (!Array.isArray(owners)) throw new Error("Could not resolve owner accounts.");

    const riskLevel = String(risk.risk_level ?? "");
    const mapping: Record<string, { level: string; decision: string }> = {
      BLOCKED: { level: "CRITICAL", decision: "BLOCK" },
      CAUTION: { level: "MEDIUM", decision: "REDUCE_RISK" },
      OBSERVE: { level: "LOW", decision: "ALLOW_REVIEW" },
    };
    const mapped = mapping[riskLevel];
    if (!mapped) throw new Error("Unrecognized operational risk level.");

    for (const owner of owners) {
      if (typeof owner.user_id !== "string") continue;
      await supabaseRequest("risk_assessments", "POST", [{
        user_id: owner.user_id,
        risk_level: mapped.level,
        decision: mapped.decision,
        rationale: `Operational data-quality assessment only; not portfolio exposure or trade authorization. ${String(risk.summary ?? "").slice(0, 700)}`,
        assessment_payload: {
          source: "V9_READ_ONLY_RISK_MONITOR",
          source_risk_level: riskLevel,
          metrics: risk.metrics,
          flags: risk.flags,
          limitations: risk.limitations ?? [],
          safety: {
            orders_enabled: false,
            wallet_access: false,
            broker_credentials_required: false,
            automated_trade_instruction: false,
          },
        },
      }]);
    }

    return response(200, {
      ok: true,
      mode: "READ ONLY",
      inserted_signals: insertedSignals,
      duplicate_signals: duplicateSignals,
      owner_risk_assessments_written: owners.length,
      orders_enabled: false,
    });
  } catch (error) {
    return response(500, {
      error: error instanceof Error ? error.message : "Internal ingestion error.",
    });
  }
});
