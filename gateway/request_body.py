"""Bound loopback requests by bytes, independently of model context tokens."""
class BodyTooLarge(ValueError):
    def __init__(self, limit, received=0, declared=None):
        self.metrics = {'limit_bytes': limit, 'received_bytes': received,
                        'declared_bytes': declared}
        super().__init__('Local gateway request body exceeds the byte limit')

    def response(self):
        limit = self.metrics['limit_bytes'] / (1024 * 1024)
        return {'error': {
            'type': 'invalid_request_error', 'code': 'local_request_body_too_large',
            'message': f'本机网关请求体超过 {limit:g} MiB 上限（包含历史图片的 Base64 数据）。'
                       '尚未发送到模型，不是 token 额度错误。请减少历史图片，或在新对话提供工作摘要；未自动重试。',
            **self.metrics}}


async def read_body(request, limit):
    declared = request.headers.get('content-length')
    try:
        declared = int(declared) if declared is not None else None
    except ValueError:
        declared = None
    if declared is not None and declared > limit:
        raise BodyTooLarge(limit, declared=declared)
    body = bytearray()
    async for part in request.stream():
        if len(body) + len(part) > limit:
            raise BodyTooLarge(limit, len(body) + len(part), declared)
        body.extend(part)
    return body
