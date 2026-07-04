import { NavLink, Route, Routes } from 'react-router-dom'
import { useI18n } from './i18n'
import Dashboard from './pages/Dashboard'
import Live from './pages/Live'
import AutoClip from './pages/AutoClip'
import Download from './pages/Download'
import Editor from './pages/Editor'
import Streamers from './pages/Streamers'
import Queue from './pages/Queue'
import Library from './pages/Library'
import BrandKits from './pages/BrandKits'
import Publish from './pages/Publish'
import Settings from './pages/Settings'

const NAV = [
  { to: '/', key: 'nav.dashboard', icon: '🏠' },
  { to: '/live', key: 'nav.live', icon: '📡' },
  { to: '/autoclip', key: 'nav.autoclip', icon: '✨' },
  { to: '/download', key: 'nav.download', icon: '⬇' },
  { to: '/editor', key: 'nav.editor', icon: '🎬' },
  { to: '/streamers', key: 'nav.streamers', icon: '🎮' },
  { to: '/queue', key: 'nav.queue', icon: '🗂' },
  { to: '/library', key: 'nav.library', icon: '📚' },
  { to: '/brandkits', key: 'nav.brandkits', icon: '🎨' },
  { to: '/publish', key: 'nav.publish', icon: '🚀' },
  { to: '/settings', key: 'nav.settings', icon: '⚙' },
]

export default function App() {
  const { t, lang, setLang } = useI18n()
  return (
    <div className="flex min-h-screen">
      <aside className="w-52 shrink-0 border-e border-slate-800 bg-slate-900 p-3">
        <div className="mb-4 flex items-center gap-2 px-2">
          <span className="text-xl font-black text-accent">KICKLIPS</span>
          <span className="text-xs text-slate-400">Studio</span>
        </div>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded px-2 py-1.5 text-sm ${
                  isActive ? 'bg-blue-600/20 font-bold text-blue-300' : 'text-slate-300 hover:bg-slate-800'
                }`
              }
            >
              <span aria-hidden>{item.icon}</span>
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
        <button
          className="btn-secondary mt-6 w-full justify-center"
          onClick={() => setLang(lang === 'he' ? 'en' : 'he')}
        >
          {lang === 'he' ? 'English' : 'עברית'}
        </button>
      </aside>
      <main className="flex-1 overflow-x-hidden p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/live" element={<Live />} />
          <Route path="/autoclip" element={<AutoClip />} />
          <Route path="/download" element={<Download />} />
          <Route path="/editor" element={<Editor />} />
          <Route path="/editor/:clipId" element={<Editor />} />
          <Route path="/streamers" element={<Streamers />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/library" element={<Library />} />
          <Route path="/brandkits" element={<BrandKits />} />
          <Route path="/publish" element={<Publish />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
