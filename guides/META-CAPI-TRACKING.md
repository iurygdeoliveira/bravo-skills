# Meta Ads Tracking — Pixel (Web) + CAPI (Server)

Guia de implementação do tracking Meta Ads com disparo duplo (client + server) usando Vercel.

---

## Arquitetura

```
Usuário abre a página
  │
  ├── [CLIENT] Meta Pixel (fbevents.js) dispara evento no browser
  │
  └── [CLIENT] JS envia POST para /api/meta-capi
        │
        └── [SERVER] Vercel Serverless Function
              ├── Enriquece com geo headers da Vercel
              └── Envia para Meta Conversions API (graph.facebook.com)
```

A deduplicação é feita pelo `event_id` — o mesmo ID é enviado tanto no Pixel (client) quanto no CAPI (server). O Meta ignora o duplicado automaticamente.

---

## 1. Pixel Client-Side (Web)

O Pixel ID vai **hardcoded no HTML** — env vars da Vercel não substituem em arquivos estáticos.

### No `<head>` do HTML:

```html
<!-- Meta Pixel -->
<script>
  !function(f,b,e,v,n,t,s)
  {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', 'SEU_PIXEL_ID_AQUI');
  fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id=SEU_PIXEL_ID_AQUI&ev=PageView&noscript=1"/></noscript>
```

---

## 2. CAPI Server-Side (Vercel Serverless)

### Arquivo: `/api/meta-capi.js`

Usa `process.env.META_PIXEL_ID` e `process.env.META_ACCESS_TOKEN`.

### Env vars na Vercel (Settings > Environment Variables):

| Nome               | Valor                          |
|--------------------|--------------------------------|
| `META_PIXEL_ID`    | ID do pixel (ex: 388497132498453) |
| `META_ACCESS_TOKEN`| Token gerado no Events Manager |

### Como gerar o Access Token:

1. Acesse [Events Manager](https://business.facebook.com/events_manager)
2. Selecione o Pixel
3. Settings > Conversions API > Generate Access Token

---

## 3. Campos `user_data` aceitos pela Meta CAPI

**IMPORTANTE**: Use exatamente estes nomes. A API rejeita campos com nomes errados.

### Campos que NÃO precisam de hash:

| Campo                | Descrição                    | Fonte                        |
|----------------------|------------------------------|------------------------------|
| `client_ip_address`  | IP do usuário                | `x-real-ip` header           |
| `client_user_agent`  | User agent do browser        | `user-agent` header          |
| `fbp`                | Cookie `_fbp` do Pixel       | Enviado pelo client JS       |
| `fbc`                | Cookie `_fbc` ou `fbclid`    | Enviado pelo client JS       |
| `external_id`        | ID externo (hashed)          | Opcional                     |

### Campos que PRECISAM de hash SHA-256 (lowercase, trim, antes de hashear):

| Campo      | Descrição              | Header da Vercel                   |
|------------|------------------------|------------------------------------|
| `ct`       | Cidade (array)         | `x-vercel-ip-city`                 |
| `st`       | Estado/região (array)  | `x-vercel-ip-country-region`       |
| `country`  | País (array)           | `x-vercel-ip-country`              |
| `em`       | Email (array)          | Coletado do usuário                |
| `ph`       | Telefone (array)       | Coletado do usuário                |
| `fn`       | Primeiro nome (array)  | Coletado do usuário                |
| `ln`       | Sobrenome (array)      | Coletado do usuário                |
| `zp`       | CEP (array)            | Coletado do usuário                |

### Erros comuns:

| Errado           | Certo      | Motivo                                  |
|------------------|------------|-----------------------------------------|
| `country_code`   | `country`  | Meta usa `country`, não `country_code`  |
| `city`           | `ct`       | Meta usa abreviações                    |
| `state`          | `st`       | Meta usa abreviações                    |
| `email`          | `em`       | Meta usa abreviações                    |
| `phone`          | `ph`       | Meta usa abreviações                    |
| Valor sem hash   | SHA-256    | PII deve ser hasheado                   |
| String simples   | `[array]`  | Campos PII são arrays                   |

---

## 4. Headers da Vercel para Geo

Headers disponíveis automaticamente em serverless functions:

| Header                          | Exemplo        |
|---------------------------------|----------------|
| `x-real-ip`                     | `189.1.2.3`    |
| `x-forwarded-for`               | `189.1.2.3`    |
| `x-vercel-ip-city`              | `Sao Paulo`    |
| `x-vercel-ip-country`           | `BR`           |
| `x-vercel-ip-country-region`    | `SP`           |
| `x-vercel-ip-latitude`          | `-23.5505`     |
| `x-vercel-ip-longitude`         | `-46.6333`     |

**Nota**: `x-real-ip` e `x-forwarded-for` NÃO devem ser hasheados — a Meta espera IP em texto puro. Apenas os campos de localização (ct, st, country) devem ser hasheados.

---

## 5. Payload da CAPI

Estrutura completa enviada para `POST https://graph.facebook.com/v21.0/{PIXEL_ID}/events`:

```json
{
  "data": [
    {
      "event_name": "PageView",
      "event_time": 1710000000,
      "event_id": "eid_1710000000_abc123",
      "event_source_url": "https://seusite.com/oferta-ds/",
      "action_source": "website",
      "user_data": {
        "client_ip_address": "189.1.2.3",
        "client_user_agent": "Mozilla/5.0...",
        "fbp": "fb.1.1710000000.1234567890",
        "fbc": "fb.1.1710000000.AbCdEf",
        "ct": ["sha256hash"],
        "st": ["sha256hash"],
        "country": ["sha256hash"]
      },
      "custom_data": {
        "content_name": "Jornada + Protocolo",
        "currency": "BRL",
        "value": 497.00
      }
    }
  ]
}
```

---

## 6. Client JS — Disparo duplo (Pixel + CAPI)

```javascript
function sendCAPI(eventName, customData) {
    const eventId = 'eid_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    const fbp = getCookie('_fbp');
    const fbc = getCookie('_fbc') || buildFbc();

    // 1. Client-side Pixel (com event_id para dedup)
    fbq('track', eventName, customData || {}, { eventID: eventId });

    // 2. Server-side CAPI
    fetch('/api/meta-capi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            event_name: eventName,
            event_id: eventId,             // mesmo ID = dedup
            event_source_url: window.location.href,
            user_data_client: {
                ...(fbp && { fbp }),
                ...(fbc && { fbc }),
            },
            ...(customData && { custom_data: customData }),
        }),
        keepalive: true,  // garante envio mesmo se a página fechar
    }).catch(function() {});
}
```

---

## 7. Eventos implementados

| Evento            | Trigger                          | custom_data                              |
|-------------------|----------------------------------|------------------------------------------|
| `PageView`        | Carregamento da página           | —                                        |
| `InitiateCheckout`| Clique nos CTAs de compra        | `content_name`, `currency`, `value`      |
| `Contact`         | Clique no botão de suporte       | `content_name: "Suporte WhatsApp"`       |

---

## 8. Checklist de deploy

- [ ] Pixel ID hardcoded no HTML (não usa env var)
- [ ] `META_PIXEL_ID` configurado nas env vars da Vercel
- [ ] `META_ACCESS_TOKEN` configurado nas env vars da Vercel
- [ ] Testar com [Meta Pixel Helper](https://chrome.google.com/webstore/detail/meta-pixel-helper) (Chrome extension)
- [ ] Verificar eventos no [Events Manager > Test Events](https://business.facebook.com/events_manager)
- [ ] Confirmar deduplicação: mesmo `event_id` aparece uma vez só no Events Manager
