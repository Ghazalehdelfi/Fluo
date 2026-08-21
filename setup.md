Deployment Steps (in order)
1. Create Lightsail instance (AWS Console)

Ubuntu 22.04, $5/mo plan
Attach a static IP
Open ports 80 and 443 in networking tab
Download the SSH key
2. Upload secrets to SSM (from your Mac)

3. SSH into the instance and run setup

4. For future code updates (from your Mac)

5. Optional: Add HTTPS (on the server, after pointing your domain)

Your secrets never touch the disk on the server — they're fetched from SSM Parameter Store at each app startup.

---

## Observability with Langfuse

Langfuse gives you per-session traces, error tracking, latency, and cost visibility for every LLM/TTS/STT call.

### Setup (free tier available at cloud.langfuse.com)

1. Sign up at https://cloud.langfuse.com and create a project
2. Copy your **Public Key** and **Secret Key** from Project Settings → API Keys
3. Add them to SSM (or your `.env` for local dev):

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com   # omit to use this default
```

If the keys are absent, the app runs normally with no observability (graceful degradation).

### What you see in Langfuse

- **Traces**: one trace per API session (start-lesson, respond, scenario, etc.)
- **Generations**: every GPT call with prompt, response, token counts, latency, and cost
- **Spans**: every TTS and STT call with duration and cost
- **Errors**: any failed call is marked ERROR with the exception message
- **User analytics**: filter by `user_id` to see a specific student's activity