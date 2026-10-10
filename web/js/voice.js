// GenAI Generated code - Start
// Browser-native voice I/O. Uses the Web Speech API so there is no server cost,
// no extra dependency, and no audio ever leaves the device for TTS.
// Speech recognition in Chrome/Edge does send audio to the browser vendor's
// service - the UI tells the user when the mic is live.

import { SPEECH_CODES } from "./i18n.js";
import { toSpeech } from "./markdown.js";

const Recognition =
  window.SpeechRecognition || window.webkitSpeechRecognition || null;

export const sttSupported = Boolean(Recognition);
export const ttsSupported = "speechSynthesis" in window;

export function createVoice({ onInterim, onFinal, onStateChange, onError } = {}) {
  let recognition = null;
  let listening = false;
  let autoSpeak = false;

  const setState = (state) => onStateChange && onStateChange(state);

  function stop() {
    if (recognition) {
      try {
        recognition.stop();
      } catch {
        /* already stopped */
      }
    }
    listening = false;
    setState("idle");
  }

  function start(langCode) {
    if (!sttSupported) {
      onError && onError("unsupported");
      return false;
    }
    if (listening) {
      stop();
      return false;
    }
    recognition = new Recognition();
    recognition.lang = SPEECH_CODES[langCode] || "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      listening = true;
      setState("listening");
    };
    recognition.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) final += result[0].transcript;
        else interim += result[0].transcript;
      }
      if (interim && onInterim) onInterim(interim);
      if (final && onFinal) onFinal(final.trim());
    };
    recognition.onerror = (event) => {
      listening = false;
      setState("idle");
      onError && onError(event.error || "error");
    };
    recognition.onend = () => {
      listening = false;
      setState("idle");
    };

    try {
      recognition.start();
      return true;
    } catch (err) {
      onError && onError(String(err));
      return false;
    }
  }

  function pickVoice(langCode) {
    if (!ttsSupported) return null;
    const target = (SPEECH_CODES[langCode] || "en-IN").toLowerCase();
    const prefix = target.split("-")[0];
    const voices = window.speechSynthesis.getVoices() || [];
    return (
      voices.find((v) => v.lang.toLowerCase() === target) ||
      voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ||
      voices.find((v) => v.lang.toLowerCase().startsWith("en")) ||
      null
    );
  }

  function speak(text, langCode) {
    if (!ttsSupported || !text) return;
    const clean = toSpeech(text).slice(0, 1200);
    if (!clean) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = SPEECH_CODES[langCode] || "en-IN";
    const voice = pickVoice(langCode);
    if (voice) utterance.voice = voice;
    utterance.rate = 0.98;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  }

  function cancelSpeech() {
    if (ttsSupported) window.speechSynthesis.cancel();
  }

  // Voice list loads asynchronously in most browsers.
  if (ttsSupported) window.speechSynthesis.onvoiceschanged = () => pickVoice("en");

  return {
    start,
    stop,
    speak,
    cancelSpeech,
    get listening() {
      return listening;
    },
    get autoSpeak() {
      return autoSpeak;
    },
    set autoSpeak(value) {
      autoSpeak = Boolean(value);
      if (!autoSpeak) cancelSpeech();
    },
  };
}
// GenAI Generated code - End
