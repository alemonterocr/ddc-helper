/// <reference types="chrome" />
import type { StateStorage } from 'zustand/middleware'

/**
 * Zustand persist-middleware adapter for chrome.storage.local.
 *
 * Values are stored as JSON strings (Zustand serialises them before calling
 * setItem, and deserialises after getItem returns).
 *
 * All methods are async — Zustand's persist middleware supports Promise-based
 * storage out of the box.
 */
const storage = typeof chrome !== "undefined" && chrome.storage ? chrome.storage.local : undefined

export const chromeStorageAdapter: StateStorage = {
  getItem: (name: string): Promise<string | null> =>
    storage
      ? storage.get(name).then((result) => {
          const value = result[name]
          return value !== undefined ? (value as string) : null
        })
      : Promise.resolve(null),

  setItem: (name: string, value: string): Promise<void> =>
    storage
      ? storage.set({ [name]: value })
      : Promise.resolve(),

  removeItem: (name: string): Promise<void> =>
    storage
      ? storage.remove(name)
      : Promise.resolve(),
}
