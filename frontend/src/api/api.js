import axios from "axios";

const API_URL = "http://127.0.0.1:8000";

export const getKpis = () =>
  axios.get(`${API_URL}/api/kpis`);

export const getYearlyPublications = () =>
  axios.get(`${API_URL}/api/publications/yearly`);

export const getPublicationTypes = () =>
  axios.get(`${API_URL}/api/publications/types`);

export const getPublicationTypesByYear = () =>
  axios.get(`${API_URL}/api/publications/types-by-year`);

export const getCollaboration = () =>
  axios.get(`${API_URL}/api/collaboration`);

export const getVenues = () =>
  axios.get(`${API_URL}/api/venues`);

export const getDataQuality = () =>
  axios.get(`${API_URL}/api/data-quality`);

export const getTopicsOverTime = () =>
  axios.get(`${API_URL}/api/topics-over-time`);