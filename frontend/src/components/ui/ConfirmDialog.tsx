'use client';

import Modal from './Modal';

interface ConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** 'warning' for caution actions, 'danger' for destructive actions */
  variant?: 'warning' | 'danger' | 'default';
  loading?: boolean;
}

const VARIANT_COLORS = {
  default: { bg: 'var(--gold-500)', hover: 'var(--gold-600)' },
  warning: { bg: '#F59E0B', hover: '#D97706' },
  danger: { bg: '#EF4444', hover: '#DC2626' },
};

export default function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title = 'Xác nhận',
  message,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Hủy',
  variant = 'default',
  loading = false,
}: ConfirmDialogProps) {
  const colors = VARIANT_COLORS[variant];

  return (
    <Modal open={open} onClose={onCancel} title={title} size="sm" persistent>
      <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {message}
      </p>

      <div className="flex gap-3 justify-end">
        <button
          onClick={onCancel}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-sm font-medium transition-colors hover:bg-white/10"
          style={{
            color: 'var(--text-secondary)',
            border: '1px solid var(--border-default)',
          }}
        >
          {cancelLabel}
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-sm font-semibold text-white transition-colors"
          style={{
            background: colors.bg,
            opacity: loading ? 0.7 : 1,
          }}
          onMouseEnter={e => (e.currentTarget.style.background = colors.hover)}
          onMouseLeave={e => (e.currentTarget.style.background = colors.bg)}
        >
          {loading ? 'Đang xử lý...' : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
