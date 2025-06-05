// API configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// Helper to build API URLs
export const apiUrl = (path: string): string => {
  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  
  // If API_BASE_URL is empty (production), use relative paths
  if (!API_BASE_URL) {
    return `/api${normalizedPath}`;
  }
  
  // For development with full URL
  return `${API_BASE_URL}/api${normalizedPath}`;
};

// Helper to get auth headers
export const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// Export base URL for cases where full control is needed
export { API_BASE_URL };