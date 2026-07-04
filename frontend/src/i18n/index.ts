import he from './he.json'
import en from './en.json'
import { create } from 'zustand'

type Lang = 'he' | 'en'
const dicts: Record<Lang, Record<string, string>> = { he, en }

interface I18nState {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string) => string
}

export const useI18n = create<I18nState>((set, get) => ({
  lang: (localStorage.getItem('lang') as Lang) || 'he',
  setLang: (lang) => {
    localStorage.setItem('lang', lang)
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr'
    set({ lang })
  },
  t: (key) => dicts[get().lang][key] ?? dicts.en[key] ?? key,
}))

// Apply direction on load.
const initial = (localStorage.getItem('lang') as Lang) || 'he'
document.documentElement.lang = initial
document.documentElement.dir = initial === 'he' ? 'rtl' : 'ltr'
