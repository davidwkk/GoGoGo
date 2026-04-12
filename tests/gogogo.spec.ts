import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const API_BASE = 'http://localhost:8000/api/v1';

// Helper: inject auth directly into localStorage (bypasses login flow entirely)
async function injectAuth(page: import('@playwright/test').Page) {
  await page.evaluate(() => {
    localStorage.setItem('access_token', 'fake-jwt');
    localStorage.setItem('user_email', 'test@test.com');
  });
}

test.describe('GoGoGo E2E Flows', () => {

  test('Login Flow: register -> redirect to chat', async ({ page, browserName }) => {
    await page.route('**/auth/register', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: 'fake-jwt', token_type: 'bearer' })
      });
    });

    await page.goto(`${BASE_URL}/login`);
    await page.getByRole('button', { name: 'Sign up' }).click();

    const uniqueEmail = `test_${browserName}_${Math.random().toString(36).slice(2, 7)}@example.com`;
    await page.getByLabel('Email').fill(uniqueEmail);
    await page.getByLabel('Username').fill('TestUser');
    await page.getByLabel('Password', { exact: true }).fill('ValidPass123!');
    await page.getByLabel('Confirm Password').fill('ValidPass123!');

    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page).toHaveURL(/\/chat/, { timeout: 10000 });
  });

  test('Guest Mode Flow: "Continue as Guest" -> redirect to chat', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.getByRole('button', { name: 'Continue as Guest' }).click();
    await expect(page).toHaveURL(/\/chat/);
  });

  test.describe('Voice Tests', () => {
    test('Voice Input Toggle: Verify mic button toggles state', async ({ page, browserName, context }) => {
      if (browserName !== 'chromium') {
        test.skip();
        return;
      }
      await context.grantPermissions(['microphone']);

      // Inject mocks for voice/audio APIs to ensure they work in headless CI
      await page.addInitScript(() => {
        // 1. Mock Web Speech API (for useASR)
        class MockSpeechRecognition {
          onstart: any = null;
          onend: any = null;
          start() { setTimeout(() => this.onstart?.(), 10); }
          stop() { setTimeout(() => this.onend?.(), 10); }
        }
        (window as any).SpeechRecognition = MockSpeechRecognition;
        (window as any).webkitSpeechRecognition = MockSpeechRecognition;

        // 2. Mock WebSocket for Live Session
        const OriginalWebSocket = window.WebSocket;
        (window as any).WebSocket = function(url: string, protocols: any) {
          if (url.includes('/live/ws')) {
            const ws: any = {
              readyState: 1,
              OPEN: 1,
              send: () => {},
              close: () => { setTimeout(() => ws.onclose?.(), 10); }
            };
            setTimeout(() => ws.onopen?.(), 10);
            return ws;
          }
          return new OriginalWebSocket(url, protocols);
        };
        (window as any).WebSocket.CONNECTING = 0;
        (window as any).WebSocket.OPEN = 1;
        (window as any).WebSocket.CLOSING = 2;
        (window as any).WebSocket.CLOSED = 3;

        // 3. Mock getUserMedia (for useLiveSession)
        if (!navigator.mediaDevices) (navigator as any).mediaDevices = {};
        navigator.mediaDevices.getUserMedia = () => Promise.resolve({
          getTracks: () => [{ stop: () => {} }]
        } as any);

        // 4. Mock AudioContext (for useLiveSession)
        class MockAudioContext {
          sampleRate = 16000;
          resume = () => Promise.resolve();
          createMediaStreamSource = () => ({ connect: () => {} });
          createScriptProcessor = () => ({ connect: () => {}, disconnect: () => {} });
          close = () => Promise.resolve();
          destination = {};
        }
        (window as any).AudioContext = MockAudioContext;
        (window as any).webkitAudioContext = MockAudioContext;
      });

      await page.goto(`${BASE_URL}/login`);
      await page.getByRole('button', { name: 'Continue as Guest' }).click();
      await expect(page.getByRole('button', { name: 'Start recording' })).toBeVisible();

      // Toggle on
      await page.getByRole('button', { name: 'Start recording' }).click();
      await expect(page.getByRole('button', { name: 'Stop recording' })).toBeVisible();

      // Toggle off
      await page.getByRole('button', { name: 'Stop recording' }).click();
      await expect(page.getByRole('button', { name: 'Start recording' })).toBeVisible();
    });
  });

  test('Chat to Trip View: Send message -> wait for AI -> navigate to TripPage -> verify renders', async ({ page }) => {
    const itineraryData = {
      destination: 'Tokyo',
      duration_days: 3,
      flights: [],
      days: [],
      estimated_total_budget_hkd: { min: 5000, max: 10000 }
    };

    const makeEvent = (payload: object) => `data: ${JSON.stringify(payload)}\n\n`;

    await page.route(`${API_BASE}/chat/sessions**`, async route => {
      await route.fulfill({ status: 200, json: { sessions: [] } });
    });

    await page.route(`${API_BASE}/chat/stream`, async route => {
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
        body: [
          makeEvent({ chunk: 'I am planning your Tokyo trip now...' }),
          makeEvent({ message_type: 'itinerary', itinerary: itineraryData }),
          makeEvent({ done: true }),
        ].join(''),
      });
    });

    await page.route(`${API_BASE}/trips`, async (route, request) => {
      if (request.method() === 'GET') {
        return route.fulfill({
          status: 200,
          json: [{ id: 1, title: 'Tokyo Trip', destination: 'Tokyo' }]
        });
      }
      return route.continue();
    });

    await page.route(`${API_BASE}/trips/1`, async route => {
      return route.fulfill({
        status: 200,
        json: { id: 1, title: 'Tokyo Trip', destination: 'Tokyo', itinerary: itineraryData }
      });
    });

    // Start on login page so localStorage is on the correct origin, then inject auth
    await page.goto(`${BASE_URL}/login`);
    await injectAuth(page);
    await page.goto(`${BASE_URL}/chat`);

    await page.getByPlaceholder('Message GoGoGo...').fill('Plan a trip to Tokyo');
    await page.getByRole('button', { name: 'Send message' }).click();
    await expect(page.getByText(/your trip plan is ready below/i)).toBeVisible({ timeout: 15000 });

    await page.goto(`${BASE_URL}/trips`);
    await expect(page.getByText('Tokyo Trip')).toBeVisible({ timeout: 10000 });
    await page.getByText('Tokyo Trip').click();
    await expect(page.getByRole('heading', { name: 'Tokyo Trip', exact: true })).toBeVisible({ timeout: 10000 });
  });

  test('Trip Detail View: Click saved trip -> verify sections render with images', async ({ page }) => {
    const kyotoItinerary = {
      destination: 'Kyoto',
      flights: [{ id: 'f1', airline: 'JAL' }],
      hotels: [{ id: 'h1', name: 'Kyoto Inn', image_url: 'https://via.placeholder.com/150' }],
      days: [{
        day_number: 1,
        date: '2026-05-01',
        morning: [{ name: 'Kinkaku-ji', image_url: 'https://via.placeholder.com/150' }]
      }]
    };

    await page.route(`${API_BASE}/trips`, async (route, request) => {
      if (request.method() === 'GET') {
        return route.fulfill({
          status: 200,
          json: [{ id: 123, title: 'Kyoto Adventures', destination: 'Kyoto' }]
        });
      }
      return route.continue();
    });

    await page.route(`${API_BASE}/trips/123`, async route => {
      return route.fulfill({
        status: 200,
        json: { id: 123, title: 'Kyoto Adventures', destination: 'Kyoto', itinerary: kyotoItinerary }
      });
    });

    // Inject auth directly — both keys required by initAuth()
    await page.goto(`${BASE_URL}/login`);
    await injectAuth(page);
    await page.goto(`${BASE_URL}/trips`);

    await expect(page.getByText('Kyoto Adventures')).toBeVisible({ timeout: 10000 });
    await page.getByText('Kyoto Adventures').click();

    await expect(page.getByText('Flight Logistics')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Daily Schedule')).toBeVisible();
    await expect(page.locator('img').first()).toBeVisible();
  });

});