<template>
  <div class="trek-chatbot-wrapper">
    <!-- Floating Circular Button with Your Bot Image -->
    <button
      class="trek-chat-toggle shadow-lg"
      @click="toggleChat"
      :class="{ 'chat-open': isOpen }"
      aria-label="Toggle Trek Assistant"
    >
      <span v-if="!isOpen" class="toggle-icon d-flex align-items-center justify-content-center position-relative">
        <img
          src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0HQXV4NPdKKOk31DN18xrMaa-53sGN3YAnXyAD1E-DQ&s=10"
          alt="Trek Bot"
          class="bot-avatar-img rounded-circle"
        />
        <span class="online-dot"></span>
      </span>
      <span v-else class="toggle-icon fs-5 fw-bold text-white">✕</span>
    </button>

    <!-- Chat Window Container -->
    <transition name="chat-slide">
      <div v-if="isOpen" class="trek-chat-window shadow-lg border-0 card">
        <!-- Header with Your Bot Image -->
        <div class="card-header trek-chat-header d-flex justify-content-between align-items-center text-white py-3 px-3">
          <div class="d-flex align-items-center gap-2">
            <img
              src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0HQXV4NPdKKOk31DN18xrMaa-53sGN3YAnXyAD1E-DQ&s=10"
              alt="Bot Avatar"
              class="header-avatar rounded-circle shadow-sm"
            />
            <div>
              <h6 class="mb-0 fw-bold">TrekFlow Guide</h6>
              <small class="text-white-50 d-flex align-items-center gap-1">
                <span class="status-indicator"></span> Online • Instant Answers
              </small>
            </div>
          </div>
          <button class="btn btn-sm btn-link text-white text-decoration-none p-0 fs-5" @click="toggleChat">
            ✕
          </button>
        </div>

        <!-- Quick Question Chips -->
        <div class="quick-chips-bar px-3 py-2 bg-light border-bottom d-flex gap-1 overflow-auto">
          <button
            v-for="(chip, idx) in quickChips"
            :key="idx"
            class="badge rounded-pill bg-white text-dark border chip-btn"
            @click="sendQuickPrompt(chip.prompt)"
          >
            {{ chip.label }}
          </button>
        </div>

        <!-- Message Body -->
        <div class="card-body trek-chat-body px-3 py-3" ref="messagesContainer">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="message-row mb-3 d-flex"
            :class="msg.sender === 'user' ? 'justify-content-end' : 'justify-content-start'"
          >
            <div class="message-bubble" :class="msg.sender">
              <div class="message-text" v-html="formatMessage(msg.text)"></div>

              <!-- Recommendation Cards -->
              <div v-if="msg.treks && msg.treks.length" class="trek-cards-container mt-2">
                <div
                  v-for="trek in msg.treks"
                  :key="trek.id"
                  class="trek-mini-card card border-0 bg-white shadow-sm mb-2 p-2"
                >
                  <div class="d-flex justify-content-between align-items-start mb-1">
                    <span class="fw-bold text-dark text-truncate" style="max-width: 170px;">{{ trek.name }}</span>
                    <span class="badge" :class="getDifficultyBadge(trek.difficulty)">
                      {{ trek.difficulty }}
                    </span>
                  </div>
                  <div class="small text-muted mb-1">
                    📍 {{ trek.location }} • ⏱️ {{ trek.duration }} Days
                  </div>
                  <div class="d-flex justify-content-between align-items-center pt-1 border-top">
                    <span class="fw-bold text-success">₹{{ trek.price?.toLocaleString('en-IN') }}</span>
                    <span class="small text-muted">🎟️ {{ trek.available_slot }} left</span>
                    <button class="btn btn-xs btn-outline-success py-0 px-2" @click="goToTrek(trek.id)">
                      View
                    </button>
                  </div>
                </div>
              </div>

              <div class="message-time text-end">
                <small>{{ msg.time }}</small>
              </div>
            </div>
          </div>

          <!-- Typing Indicator -->
          <div v-if="loading" class="d-flex justify-content-start mb-2">
            <div class="typing-bubble bg-light p-2 rounded-3 shadow-sm">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>

        <!-- Input Footer with Visible Black Text -->
        <div class="card-footer bg-white border-top p-2">
          <form @submit.prevent="sendMessage" class="d-flex gap-2">
            <input
              type="text"
              class="form-control form-control-sm chat-input"
              placeholder="Ask about treks, budget, dates..."
              v-model="inputQuery"
              :disabled="loading"
              ref="chatInputRef"
            />
            <button
              type="submit"
              class="btn btn-success btn-sm px-3 send-btn"
              :disabled="loading || !inputQuery.trim()"
            >
              ➤
            </button>
          </form>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue';
import axios from 'axios';
import { useRouter } from 'vue-router';

const router = useRouter();

const isOpen = ref(false);
const inputQuery = ref('');
const loading = ref(false);
const messagesContainer = ref(null);
const chatInputRef = ref(null);

const quickChips = [
  { label: '🏔️ Easy Treks', prompt: 'Show me easy treks for beginners' },
  { label: '💰 Budget Friendly', prompt: 'Which treks are under ₹5,000?' },
  { label: '📅 Upcoming', prompt: 'Show me all upcoming available treks' },
  { label: '❓ How to Book', prompt: 'How does the booking process work?' },
  { label: '📞 Contact', prompt: 'How can I contact support?' }
];

const messages = ref([
  {
    sender: 'bot',
    text: "👋 Hi! I'm your **TrekFlow AI Guide**.\n\nAsk me about upcoming treks, prices, difficulty levels, route details, or how to book your spot!",
    treks: [],
    time: getCurrentTime()
  }
]);

function getCurrentTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function toggleChat() {
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    nextTick(() => {
      scrollToBottom();
      chatInputRef.value?.focus();
    });
  }
}

function sendQuickPrompt(prompt) {
  inputQuery.value = prompt;
  sendMessage();
}

async function sendMessage() {
  const query = inputQuery.value.trim();
  if (!query || loading.value) return;

  messages.value.push({
    sender: 'user',
    text: query,
    treks: [],
    time: getCurrentTime()
  });

  inputQuery.value = '';
  loading.value = true;
  await nextTick();
  scrollToBottom();

  try {
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000/api';
    const res = await axios.post(`${apiBase}/chat`, { message: query });
    messages.value.push({
      sender: 'bot',
      text: res.data.reply || "Here is what I found for you:",
      treks: res.data.recommended_treks || [],
      time: getCurrentTime()
    });
  } catch (err) {
    messages.value.push({
      sender: 'bot',
      text: "Sorry, I had trouble connecting to the backend server. Please ensure Flask is running on port 5000!",
      treks: [],
      time: getCurrentTime()
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

function formatMessage(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>');
}

function getDifficultyBadge(diff) {
  const val = String(diff).toLowerCase();
  if (val === 'easy') return 'bg-success';
  if (val === 'moderate') return 'bg-warning text-dark';
  return 'bg-danger';
}

function goToTrek(trekId) {
  isOpen.value = false;
  router.push('/browse-trekking');
}
</script>

<style scoped>
.trek-chatbot-wrapper {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  font-family: system-ui, -apple-system, sans-serif;
}

/* Floating Toggle Button */
.trek-chat-toggle {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #198754, #0f5132);
  color: #ffffff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  padding: 0;
  overflow: visible;
}

.trek-chat-toggle:hover {
  transform: scale(1.08);
  box-shadow: 0 8px 24px rgba(25, 135, 84, 0.5) !important;
}

/* Custom Bot Avatar Image */
.bot-avatar-img {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 50%;
  border: 2px solid #ffffff;
}

.online-dot {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 13px;
  height: 13px;
  background-color: #20c997;
  border: 2px solid #ffffff;
  border-radius: 50%;
}

.trek-chat-window {
  position: absolute;
  bottom: 74px;
  right: 0;
  width: 360px;
  max-width: 90vw;
  height: 530px;
  max-height: 80vh;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.trek-chat-header {
  background: linear-gradient(135deg, #198754, #0f5132);
}

/* Header Avatar Image */
.header-avatar {
  width: 38px;
  height: 38px;
  object-fit: cover;
  border-radius: 50%;
  border: 2px solid #ffffff;
}

.status-indicator {
  display: inline-block;
  width: 7px;
  height: 7px;
  background-color: #20c997;
  border-radius: 50%;
}

.quick-chips-bar {
  white-space: nowrap;
}

.chip-btn {
  font-size: 0.75rem;
  padding: 5px 9px;
  cursor: pointer;
  color: #212529 !important;
  background-color: #ffffff !important;
  transition: all 0.15s ease;
}

.chip-btn:hover {
  background-color: #198754 !important;
  color: #ffffff !important;
  border-color: #198754 !important;
}

.trek-chat-body {
  flex: 1;
  overflow-y: auto;
  background-color: #f8f9fa;
}

.message-bubble {
  max-width: 82%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 0.88rem;
  line-height: 1.45;
}

.message-bubble.user {
  background-color: #198754;
  color: #ffffff !important;
  border-bottom-right-radius: 2px;
}

.message-bubble.bot {
  background-color: #ffffff;
  color: #111827 !important;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 2px;
}

.message-bubble.bot .message-text {
  color: #111827 !important;
}

.message-time {
  font-size: 0.68rem;
  opacity: 0.65;
  margin-top: 4px;
}

.trek-mini-card {
  border: 1px solid #e2e8f0 !important;
  border-radius: 8px;
  color: #111827 !important;
}

.btn-xs {
  font-size: 0.72rem;
  padding: 2px 7px;
}

/* 100% Solid Black Typed Text */
.chat-input {
  color: #000000 !important;
  background-color: #ffffff !important;
  border: 1px solid #ced4da !important;
  font-size: 0.9rem !important;
}

.chat-input:focus {
  color: #000000 !important;
  background-color: #ffffff !important;
  border-color: #198754 !important;
  box-shadow: 0 0 0 0.2rem rgba(25, 135, 84, 0.25) !important;
}

.chat-input::placeholder {
  color: #6c757d !important;
  opacity: 1 !important;
}

.typing-bubble {
  display: flex;
  gap: 4px;
  align-items: center;
}

.typing-bubble .dot {
  width: 6px;
  height: 6px;
  background-color: #6c757d;
  border-radius: 50%;
  animation: bounce 1.3s infinite ease-in-out;
}

.typing-bubble .dot:nth-child(2) {
  animation-delay: 0.2s;
}
.typing-bubble .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(18px) scale(0.96);
}
</style>