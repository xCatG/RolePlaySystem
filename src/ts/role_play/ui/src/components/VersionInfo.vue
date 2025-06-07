<template>
  <div class="version-info">
    <span>{{ versionText }}</span>
  </div>
</template>

<script>
export default {
  name: 'VersionInfo',
  computed: {
    versionText() {
      const version = import.meta.env.VITE_APP_VERSION || 'dev';
      
      // For dev builds, just show "dev build"
      if (version === 'dev') {
        return 'dev build';
      }
      
      // For tagged versions, show the version
      const buildDate = import.meta.env.VITE_BUILD_DATE || '';
      
      if (buildDate) {
        const date = new Date(buildDate);
        const formattedDate = date.toLocaleDateString('en-US', { 
          month: 'short', 
          day: 'numeric', 
          year: 'numeric' 
        });
        return `${version} • ${formattedDate}`;
      }
      
      return version;
    }
  }
}
</script>

<style scoped>
.version-info {
  font-size: 0.75rem;
  color: #6c757d;
  opacity: 0.6;
  text-align: center;
  padding: 8px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
}
</style>