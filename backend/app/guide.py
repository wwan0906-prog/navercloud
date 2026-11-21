"""결과 조합: 판정 결과 → 맞춤형 보완 안내문(guide_message) + 읽어주기 문장(guide_text)"""
from __future__ import annotations


def josa(word: str, with_batchim: str, without: str) -> str:
    """받침 유무에 맞는 조사를 붙입니다. 예: 위치를 / 사항을, 유형으로 / 분야로"""
    last = word.rstrip()[-1:] if word else ''
    if not ('가' <= last <= '힣'):
        return word + with_batchim
    jong = (ord(last) - 0xAC00) % 28
    if with_batchim == '으로' and jong == 8:      # ㄹ 받침은 '로'
        return word + without
    return word + (with_batchim if jong else without)


def compose_message(category: dict | None, category_label: str, checks: list[dict],
                    complete: bool) -> str:
    if category is None:
        return (f"'{category_label}' 분야는 아직 안내 기준이 없습니다. "
                '아래 공식 채널로 접수해 주세요.')
    if not checks:
        return (f"'{category['name']}' 분야의 필수 정보 기준은 아직 준비 중입니다. "
                '아래 공식 채널로 접수해 주세요.')
    if complete:
        return '필요한 정보가 모두 들어 있습니다. 아래 공식 채널로 바로 접수해 주세요.'

    todo = [c for c in checks if c['status'] in ('missing', 'insufficient')]
    labels = [c['label'] for c in todo]
    names = ', '.join(labels[:-1] + [josa(labels[-1], '을', '를')])
    examples = [f"{c['label']}: {c['example']}" for c in todo if c.get('example')][:2]
    message = f'담당 부서가 바로 처리할 수 있도록 {names} 보완해 주세요.'
    if examples:
        message += ' (예: ' + ' / '.join(examples) + ')'
    return message


def compose_speech(category_name: str, message: str, channel: dict | None) -> str:
    parts = [f'{category_name} 분야 민원입니다.', message.split(' (예:')[0]]
    if channel:
        phone = f', 전화 {channel["phone"]}번' if channel.get('phone') else ''
        parts.append(f'접수는 {channel["agency"]}{phone}에서 할 수 있습니다.')
    return ' '.join(parts)
