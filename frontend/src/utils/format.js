import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

export function formatTime(t) {
  if (!t) return '-'
  try {
    return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
  } catch {
    return t
  }
}

export function formatShortTime(t) {
  if (!t) return '-'
  try {
    return dayjs(t).format('MM-DD HH:mm')
  } catch {
    return t
  }
}
