import { X } from 'lucide-react'
import { createPortal } from 'react-dom'

const STEPS = [
  {
    title: '登入',
    body: '使用 Google 帳號登入。本地測試也可以用 Email/Password 表單，不需要額外設定。',
  },
  {
    title: '建立專案',
    body: '在「我的專案」頁面輸入名稱並建立。每個專案的文件、對話、圖片彼此獨立，不會互相看到。',
  },
  {
    title: '上傳工程文件（Documents）',
    body: '上傳 PDF，系統會自動解析文字、分塊，並建立向量索引，供後續問答使用。',
  },
  {
    title: '文件問答（Chat）',
    body: '針對已上傳的文件用自然語言提問，答案會附上來源文件與頁碼；文件裡查不到的問題，會明確告知沒有足夠資訊，不會亂猜。',
  },
  {
    title: '圖片分析（Vision）',
    body: '上傳工程圖片，由 Claude Vision 分析並標註可觀察到的重點；不會對結構安全、施工品質或法規合規做未經證據支持的斷言。',
  },
  {
    title: 'Agent 整合助理',
    body: '用自然語言請 Agent 搜尋文件、查看圖片分析、整理成會議摘要，也可以直接在對話框附加圖片一起問。Agent 會自行判斷需要用到哪些工具。',
  },
  {
    title: 'Email 確認寄送',
    body: '請 Agent 草擬 email 後，畫面會顯示 Preview 卡片列出收件人／主旨／內容；Agent 永遠不會自動寄出，需要手動點擊 Confirm & Send 才會真正送出。',
  },
  {
    title: '追蹤紀錄（Activity）',
    body: '查看這個專案從登入、上傳、檢索到寄信的完整操作紀錄。',
  },
]

export default function HelpModal({ open, onClose }) {
  if (!open) return null

  // Portaled to <body> -- HelpModal is rendered via HeaderActions inside
  // <Header>, which has backdrop-blur (backdrop-filter). A filter/
  // backdrop-filter on an ancestor creates a new containing block for
  // position:fixed descendants, so without the portal this overlay would
  // be sized/positioned relative to the thin header bar instead of the
  // real viewport.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-card bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">使用說明</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            aria-label="關閉"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mb-4 text-sm text-slate-600">
          這不是一個聊天機器人，而是一條完整的工程 pipeline，從文件檢索、圖片分析到 Email
          寄送，串起以下幾個步驟：
        </p>

        <ol className="space-y-3">
          {STEPS.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-600">
                {i + 1}
              </span>
              <div>
                <p className="text-sm font-medium text-slate-900">{step.title}</p>
                <p className="mt-0.5 text-sm text-slate-600">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>,
    document.body
  )
}
