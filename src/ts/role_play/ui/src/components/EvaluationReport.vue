<template>
  <div class="report-container">
    <h2>Evaluation Report</h2>
    <p><strong>Overall Score:</strong> {{ report.overall_score }}</p>
    <p><strong>Human Review Recommended:</strong> {{ report.human_review_recommended ? 'Yes' : 'No' }}</p>

    <h3>Overall Assessment</h3>
    <p>{{ report.overall_assessment }}</p>

    <h3>Key Strengths Demonstrated</h3>
    <ul>
      <li v-for="(item, idx) in report.key_strengths_demonstrated" :key="idx">{{ item }}</li>
    </ul>

    <h3>Key Areas For Development</h3>
    <ul>
      <li v-for="(item, idx) in report.key_areas_for_development" :key="idx">{{ item }}</li>
    </ul>

    <h3>Actionable Next Steps</h3>
    <ul>
      <li v-for="(item, idx) in report.actionable_next_steps" :key="idx">{{ item }}</li>
    </ul>

    <h3>Progress Notes From Past Feedback</h3>
    <p>{{ report.progress_notes_from_past_feedback }}</p>

    <button class="close-btn" @click="$emit('close')">Close</button>
  </div>
</template>

<script lang="ts" setup>
import type { FinalReviewReport } from '../types/evaluation';
import { defineProps, defineEmits } from 'vue';

const props = defineProps<{ report: FinalReviewReport }>();
const emit = defineEmits<{ close: [] }>();
</script>

<style scoped>
.report-container {
  background: white;
  padding: 20px;
  border-radius: 8px;
  max-width: 600px;
  margin: 0 auto;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
.close-btn {
  margin-top: 20px;
}
</style>
