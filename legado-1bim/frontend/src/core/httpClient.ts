import axios from 'axios'
import { config } from './config'

const REQUEST_TIMEOUT_MS = 10_000

export const httpClient = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: REQUEST_TIMEOUT_MS,
})
