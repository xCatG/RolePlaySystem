<template>
  <div v-if="isLoading" class="loading">Loading report...</div>
  <div v-else-if="error" class="error-message">
    <p>Error fetching evaluation report: {{ error.message }}</p>
    <button @click="fetchReport">Retry</button>
  </div>
  <div v-else-if="report" class="evaluation-report">
    <h2>Evaluation Report for Session: {{ report.chat_session_id }}</h2>

    <section class="overall-score">
      <h3>Overall Score</h3>
      <p :class="scoreClass">{{ report.overall_score.toFixed(2) }} / 1.00</p>
      <p v-if="report.human_review_recommended" class="review-flag">
        🚩 Human review recommended
      </p>
    </section>

    <section class="assessment">
      <h3>Overall Assessment</h3>
      <p>{{ report.overall_assessment }}</p>
    </section>

    <section class="strengths">
      <h3>Key Strengths Demonstrated</h3>
      <ul>
        <li v-for="(strength, index) in report.key_strengths_demonstrated" :key="`strength-${index}`">
          {{ strength }}
        </li>
      </ul>
    </section>

    <section class="areas-for-development">
      <h3>Key Areas for Development</h3>
      <ul>
        <li v-for="(area, index) in report.key_areas_for_development" :key="`area-${index}`">
          {{ area }}
        </li>
      </ul>
    </section>

    <section class="next-steps">
      <h3>Actionable Next Steps</h3>
      <ul>
        <li v-for="(step, index) in report.actionable_next_steps" :key="`step-${index}`">
          {{ step }}
        </li>
      </ul>
    </section>

    <section class="progress-notes">
      <h3>Progress Notes from Past Feedback</h3>
      <p>{{ report.progress_notes_from_past_feedback }}</p>
    </section>
  </div>
  <div v-else class="no-report">
    No report data available.
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue';
import { chatApi } from '../services/chatApi'; // Adjusted path
import type { FinalReviewReport } from '../types/evaluation'; // Adjusted path

const props = defineProps<{
  sessionId: string | null;
}>();

const report = ref<FinalReviewReport | null>(null);
const isLoading = ref(false);
const error = ref<Error | null>(null);

const fetchReport = async () => {
  if (!props.sessionId) {
    report.value = null;
    error.value = null;
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  error.value = null;
  try {
    report.value = await chatApi.getEvaluationReport(props.sessionId);
  } catch (e) {
    console.error('Failed to fetch evaluation report:', e);
    error.value = e instanceof Error ? e : new Error('An unknown error occurred');
  } finally {
    isLoading.value = false;
  }
};

watch(() => props.sessionId, (newSessionId) => {
  if (newSessionId) {
    fetchReport();
  } else {
    report.value = null; // Clear report if sessionId becomes null
  }
}, { immediate: true }); // `immediate: true` will trigger fetchReport on component mount if sessionId is already set.

// For older Vue versions or if `immediate` is not desired with onMounted:
// onMounted(() => {
//   if (props.sessionId) {
//     fetchReport();
//   }
// });

const scoreClass = computed(() => {
  if (!report.value) return '';
  if (report.value.overall_score >= 0.8) return 'score-high';
  if (report.value.overall_score >= 0.5) return 'score-medium';
  return 'score-low';
});

</script>

<style scoped>
.evaluation-report {
  font-family: sans-serif;
  padding: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
  max-width: 800px;
  margin: 20px auto;
  background-color: #f9f9f9;
}

.evaluation-report h2 {
  text-align: center;
  color: #333;
  margin-bottom: 20px;
}

.evaluation-report section {
  margin-bottom: 25px;
  padding: 15px;
  background-color: #fff;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.evaluation-report h3 {
  color: #555;
  border-bottom: 2px solid #eee;
  padding-bottom: 8px;
  margin-top: 0;
}

.evaluation-report ul {
  list-style-type: disc;
  padding-left: 20px;
}

.evaluation-report li {
  margin-bottom: 8px;
  line-height: 1.6;
}

.loading, .error-message, .no-report {
  text-align: center;
  padding: 20px;
  font-size: 1.2em;
  color: #777;
}

.error-message button {
  margin-top: 10px;
  padding: 8px 15px;
  cursor: pointer;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
}

.error-message button:hover {
  background-color: #0056b3;
}

.review-flag {
  color: #d9534f; /* Bootstrap's text-danger color */
  font-weight: bold;
  margin-top: 5px;
}

.overall-score p {
  font-size: 1.5em;
  font-weight: bold;
  text-align: center;
}

.score-high {
  color: #5cb85c; /* Bootstrap's text-success */
}
.score-medium {
  color: #f0ad4e; /* Bootstrap's text-warning */
}
.score-low {
  color: #d9534f; /* Bootstrap's text-danger */
}
</style>
