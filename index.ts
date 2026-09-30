// Higgsfield API example: Seedance 2.5 text-to-video via the official SDK (v2 client).
// Credentials are read from HF_CREDENTIALS ("key-id:key-secret") in .env.local. Never printed.
import { config as loadEnv } from 'dotenv';
import { createHiggsfieldClient } from '@higgsfield/client/v2';

loadEnv({ path: '.env.local' });

const credentials = process.env.HF_CREDENTIALS;
if (!credentials || !credentials.includes(':')) {
  console.error('Missing HF_CREDENTIALS in .env.local (expected key-id:key-secret).');
  process.exit(1);
}

const client = createHiggsfieldClient({ credentials });

async function main(): Promise<void> {
  const result = await client.subscribe('bytedance/seedance-2.5/text-to-video', {
    input: {
      prompt: 'A cinematic scene at sunset',
      duration: 5,
      resolution: '720p',
      aspect_ratio: '16:9',
    },
    withPolling: true,
  });

  const status = String(result.status);
  switch (status) {
    case 'completed': {
      const url = result.video?.url;
      if (!url) {
        console.error(`Request ${result.request_id} completed but returned no video URL.`);
        process.exit(1);
      }
      console.log(`Video URL: ${url}`);
      return;
    }
    case 'nsfw':
      console.error(`Request ${result.request_id} was rejected by moderation (nsfw). Credits are refunded.`);
      process.exit(2);
    case 'failed':
      console.error(`Request ${result.request_id} failed. Credits are refunded.`);
      process.exit(3);
    case 'canceled':
    case 'cancelled':
      console.error(`Request ${result.request_id} was canceled.`);
      process.exit(4);
    default:
      console.error(`Request ${result.request_id} ended with unexpected status: ${status}.`);
      process.exit(5);
  }
}

main().catch((err: unknown) => {
  // Print only the message; never include headers/credentials.
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`Higgsfield request error: ${msg.replace(credentials!, '[redacted]')}`);
  process.exit(6);
});
