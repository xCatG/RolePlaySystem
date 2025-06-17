<template>
  <div class="evaluation-report-overlay" @click.self="$emit('close')">
    <div class="evaluation-report">
      <div class="report-header">
        <h1>{{ $t('evaluation.title') }}</h1>
        <button @click="$emit('close')" class="close-button">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
        <p>{{ $t('evaluation.loading') }}</p>
      </div>

      <div v-else-if="report" class="report-content">
        <section class="score-section">
          <div class="score-card">
            <h3>{{ $t('evaluation.overallScore') }}</h3>
            <div class="score-value">{{ (report.overall_score * 100).toFixed(0) }}%</div>
            <div class="score-bar">
              <div class="score-fill" :style="{ width: `${report.overall_score * 100}%` }"></div>
            </div>
          </div>
          
          <div v-if="report.human_review_recommended" class="review-notice">
            <span class="icon">⚠️</span>
            <span>{{ $t('evaluation.humanReviewRecommended') }}: {{ $t('evaluation.yes') }}</span>
          </div>
        </section>

        <section class="assessment-section">
          <h2>{{ $t('evaluation.overallAssessment') }}</h2>
          <p class="assessment-text">{{ report.overall_assessment }}</p>
        </section>

        <section class="list-section">
          <h2>{{ $t('evaluation.keyStrengths') }}</h2>
          <ul class="styled-list">
            <li v-for="(strength, index) in report.key_strengths_demonstrated" :key="`strength-${index}`">
              {{ strength }}
            </li>
          </ul>
        </section>

        <section class="list-section">
          <h2>{{ $t('evaluation.areasForDevelopment') }}</h2>
          <ul class="styled-list development-areas">
            <li v-for="(area, index) in report.key_areas_for_development" :key="`area-${index}`">
              {{ area }}
            </li>
          </ul>
        </section>

        <section class="list-section">
          <h2>{{ $t('evaluation.actionableNextSteps') }}</h2>
          <ol class="styled-list next-steps">
            <li v-for="(step, index) in report.actionable_next_steps" :key="`step-${index}`">
              {{ step }}
            </li>
          </ol>
        </section>

        <section v-if="report.progress_notes_from_past_feedback" class="progress-section">
          <h2>{{ $t('evaluation.progressNotes') }}</h2>
          <p class="progress-text">{{ report.progress_notes_from_past_feedback }}</p>
        </section>

        <div class="action-buttons">
          <button class="secondary-button" disabled>
            {{ $t('evaluation.downloadPDF') }} ({{ $t('evaluation.comingSoonTitle') }})
          </button>
          <button class="secondary-button" disabled>
            {{ $t('evaluation.share') }} ({{ $t('evaluation.comingSoonTitle') }})
          </button>
        </div>
      </div>

      <div v-else class="error-container">
        <p>{{ error || 'Failed to load evaluation report' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FinalReviewReport } from '@/types/evaluation';

defineProps<{
  report: FinalReviewReport | null;
  loading: boolean;
  error: string | null;
}>();

defineEmits<{
  close: [];
}>();
</script>

<style scoped>
.evaluation-report-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
  backdrop-filter: blur(4px);
}

.evaluation-report {
  background: var(--color-background, #ffffff);
  border-radius: 12px;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  min-height: 400px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
  transform: translateY(0);
  animation: modalSlideIn 0.3s ease-out;
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 24px 24px 24px;
  border-bottom: 1px solid var(--color-border, #e9ecef);
  background: var(--color-background, #ffffff);
  position: sticky;
  top: 0;
  z-index: 10;
}

.report-header h1 {
  margin: 0;
  font-size: 24px;
  color: var(--color-heading);
  flex: 1;
}

.close-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  color: var(--color-text, #6c757d);
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-left: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
}

.close-button:hover {
  background-color: var(--color-background-soft, #f8f9fa);
  color: var(--color-text, #495057);
}

.close-button:active {
  transform: scale(0.95);
}

.close-button svg {
  width: 20px;
  height: 20px;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  gap: 20px;
  min-height: 300px;
  background: var(--color-background, #ffffff);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.report-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: var(--color-background, #ffffff);
}

.score-section {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 32px;
}

.score-card {
  flex: 1;
  background: var(--color-background-soft, #f8f9fa);
  padding: 24px;
  border-radius: 8px;
}

.score-card h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: var(--color-text-secondary);
}

.score-value {
  font-size: 48px;
  font-weight: bold;
  color: var(--color-primary, #007bff);
  margin-bottom: 12px;
}

.score-bar {
  height: 8px;
  background: var(--color-border, #e9ecef);
  border-radius: 4px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: var(--color-primary, #007bff);
  transition: width 0.6s ease;
}

.review-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fff4e5;
  border: 1px solid #ffb800;
  border-radius: 8px;
  color: #b87c00;
}

.assessment-section,
.list-section,
.progress-section {
  margin-bottom: 32px;
}

.assessment-section h2,
.list-section h2,
.progress-section h2 {
  margin: 0 0 16px 0;
  font-size: 20px;
  color: var(--color-heading);
}

.assessment-text,
.progress-text {
  line-height: 1.6;
  color: var(--color-text);
}

.styled-list {
  margin: 0;
  padding-left: 24px;
}

.styled-list li {
  margin-bottom: 12px;
  line-height: 1.6;
  color: var(--color-text);
}

.styled-list li::marker {
  color: var(--color-primary);
}

.development-areas li::marker {
  color: #dc3545;
}

.next-steps {
  counter-reset: steps;
  list-style: none;
  padding-left: 0;
}

.next-steps li {
  counter-increment: steps;
  position: relative;
  padding-left: 40px;
}

.next-steps li::before {
  content: counter(steps);
  position: absolute;
  left: 0;
  top: 0;
  width: 28px;
  height: 28px;
  background: var(--color-primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid var(--color-border);
}

.secondary-button {
  padding: 10px 20px;
  background: var(--color-background-soft);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.secondary-button:hover:not(:disabled) {
  background: var(--color-background-mute);
}

.secondary-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-container {
  padding: 60px;
  text-align: center;
  color: var(--color-error, #dc3545);
  background: var(--color-background, #ffffff);
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 640px) {
  .evaluation-report {
    max-height: 100vh;
    border-radius: 0;
  }

  .score-section {
    flex-direction: column;
  }

  .score-value {
    font-size: 36px;
  }
}
</style>