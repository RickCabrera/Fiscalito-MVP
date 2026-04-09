/** Servicio de chat de voz para Fiscalito — STT, Chat, TTS, grabación y VAD */

import type { UserProfile } from '../context/ProfileContext';

const OPENAI_API_KEY = import.meta.env.VITE_OPENAI_API_KEY as string;

// ── Tipos ──

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

// ── Estado interno de grabación y reproducción ──

let mediaRecorder: MediaRecorder | null = null;
let recordedChunks: Blob[] = [];

let currentAudioSource: AudioBufferSourceNode | null = null;
let currentAudioCtx: AudioContext | null = null;

// ── 1. SPEECH TO TEXT ──

export async function transcribeAudio(audioBlob: Blob): Promise<string> {
  try {
    const form = new FormData();
    form.append('file', audioBlob, 'audio.webm');
    form.append('model', 'whisper-1');
    form.append('language', 'es');

    const res = await fetch('https://api.openai.com/v1/audio/transcriptions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${OPENAI_API_KEY}` },
      body: form,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`Whisper error (${res.status}): ${body}`);
    }

    const data = await res.json();
    return data.text ?? '';
  } catch (e) {
    if (e instanceof Error && e.message.startsWith('Whisper error')) throw e;
    throw new Error('No se pudo transcribir el audio. Verifica tu conexión e intenta de nuevo.');
  }
}

// ── 2. CHAT ──

function buildSystemPrompt(userProfile: UserProfile, historialResumen: string): string {
  return `Eres Fiscalito, un asistente fiscal mexicano amigable con voz propia. Hablas de forma conversacional, clara y concisa (respuestas cortas de máximo 3 oraciones para voz).
Datos del usuario actual:
- Nombre: ${userProfile.nombre || 'No proporcionado'}
- RFC: ${userProfile.rfc || 'No proporcionado'}
- Tipo: ${userProfile.contributorType || 'No definido'}
- Régimen: ${userProfile.regimen || 'No definido'}
- Actividad: ${userProfile.actividad || 'No proporcionada'}
Historial reciente: ${historialResumen || 'Sin historial aún.'}
Cuando expliques el proyecto Fiscalito preséntalo con entusiasmo como el ecosistema fiscal más innovador de México.`;
}

export async function sendMessage(
  messages: ChatMessage[],
  userProfile: UserProfile,
  historialResumen: string,
): Promise<string> {
  try {
    const systemMsg: ChatMessage = {
      role: 'system',
      content: buildSystemPrompt(userProfile, historialResumen),
    };

    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [systemMsg, ...messages],
        max_tokens: 300,
        temperature: 0.7,
      }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`Chat error (${res.status}): ${body}`);
    }

    const data = await res.json();
    return data.choices?.[0]?.message?.content ?? '';
  } catch (e) {
    if (e instanceof Error && e.message.startsWith('Chat error')) throw e;
    throw new Error('No se pudo obtener respuesta del asistente.');
  }
}

// ── 3. TEXT TO SPEECH ──

export async function speakText(text: string): Promise<void> {
  try {
    stopSpeaking();

    const res = await fetch('https://api.openai.com/v1/audio/speech', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'tts-1',
        input: text,
        voice: 'nova',
        response_format: 'mp3',
      }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`TTS error (${res.status}): ${body}`);
    }

    const arrayBuffer = await res.arrayBuffer();
    const audioCtx = new AudioContext();
    currentAudioCtx = audioCtx;

    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);
    currentAudioSource = source;

    return new Promise<void>((resolve) => {
      source.onended = () => {
        currentAudioSource = null;
        currentAudioCtx = null;
        resolve();
      };
      source.start();
    });
  } catch (e) {
    currentAudioSource = null;
    currentAudioCtx = null;
    if (e instanceof Error && e.message.startsWith('TTS error')) throw e;
    throw new Error('No se pudo reproducir la respuesta de voz.');
  }
}

export function stopSpeaking(): void {
  if (currentAudioSource) {
    try { currentAudioSource.stop(); } catch { /* ya detenido */ }
    currentAudioSource = null;
  }
  if (currentAudioCtx) {
    try { currentAudioCtx.close(); } catch { /* ya cerrado */ }
    currentAudioCtx = null;
  }
}

// ── 4. GRABACIÓN DE AUDIO ──

function getSupportedMimeType(): string {
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/ogg')) return 'audio/ogg';
  return '';
}

export async function startRecording(): Promise<void> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = getSupportedMimeType();

    recordedChunks = [];
    mediaRecorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.start();
  } catch (e) {
    throw new Error('No se pudo acceder al micrófono. Verifica los permisos del navegador.');
  }
}

export async function stopRecording(): Promise<Blob> {
  return new Promise((resolve, reject) => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      reject(new Error('No hay grabación activa.'));
      return;
    }

    mediaRecorder.onstop = () => {
      const mimeType = mediaRecorder?.mimeType || 'audio/webm';
      const blob = new Blob(recordedChunks, { type: mimeType });
      recordedChunks = [];

      // Liberar tracks del micrófono
      mediaRecorder?.stream.getTracks().forEach((t) => t.stop());
      mediaRecorder = null;

      resolve(blob);
    };

    mediaRecorder.stop();
  });
}

// ── 5. VAD SIMPLE (detección de silencio) ──

let vadAudioCtx: AudioContext | null = null;
let vadStream: MediaStream | null = null;
let vadAnimFrame: number | null = null;

export function detectSilence(onSilence: () => void, threshold: number = 2000): () => void {
  let silenceStart: number | null = null;
  let stopped = false;

  (async () => {
    try {
      vadStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      vadAudioCtx = new AudioContext();

      const source = vadAudioCtx.createMediaStreamSource(vadStream);
      const analyser = vadAudioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const SILENCE_THRESHOLD = 15; // amplitud mínima para considerar "sonido"

      const check = () => {
        if (stopped) return;

        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((sum, v) => sum + v, 0) / dataArray.length;

        if (avg < SILENCE_THRESHOLD) {
          if (silenceStart === null) silenceStart = Date.now();
          else if (Date.now() - silenceStart >= threshold) {
            onSilence();
            silenceStart = null; // resetear para no llamar repetido
          }
        } else {
          silenceStart = null;
        }

        vadAnimFrame = requestAnimationFrame(check);
      };

      vadAnimFrame = requestAnimationFrame(check);
    } catch {
      // Sin acceso al micrófono — VAD no funciona
    }
  })();

  // Retorna función de cleanup
  return () => {
    stopped = true;
    if (vadAnimFrame !== null) cancelAnimationFrame(vadAnimFrame);
    vadStream?.getTracks().forEach((t) => t.stop());
    vadStream = null;
    if (vadAudioCtx) {
      try { vadAudioCtx.close(); } catch { /* ya cerrado */ }
      vadAudioCtx = null;
    }
    vadAnimFrame = null;
  };
}
