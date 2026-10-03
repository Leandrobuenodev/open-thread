# Open Thread — DEV delivery and partial product verification

Environment identifiers and private evidence links are placeholders in this public copy.
This is a recorded validation report, not a claim that authenticated E2E passed.

Data: 2026-10-02. Relatório local produzido após a entrega automática #46.
Cloud delivery e verificações não interativas concluídas. A validação autenticada
do produto permanece **MANUAL TEST REQUIRED**: as ferramentas desta execução
não têm uma sessão Microsoft do usuário. Nenhum token foi fabricado e nenhuma
inferência Foundry foi executada nesta rodada.

## Release efetivamente publicada

| Campo | Evidência |
| --- | --- |
| Pipeline | [Open Thread #46](https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>/Open%20Thread/_build/results?buildId=46), completed / succeeded |
| Evento | `individualCI`, gerado automaticamente pelo merge; sem queue manual |
| Branch | `refs/heads/develop` |
| Commit | `047b91d0870878c6d7717fa372dc1ddd17e4e309` |
| Image tag | `openthread-backend:047b91d0870878c6d7717fa372dc1ddd17e4e309-46` |
| Digest | `sha256:d730730c51e860543d4490030d5d34162f9df5c59ac3744b144900799486b285` |
| ACR | `<ACR_NAME>.azurecr.io`, Basic, admin disabled |
| ACA | `<CONTAINER_APP_NAME>` |
| Revision | `<CONTAINER_APP_NAME>--0000006`, Healthy, active, 100% traffic |
| ARM deployment | `openthread-backend-46`, Succeeded |
| SWA | [Frontend DEV](https://<DEV_FRONTEND_HOST>) |
| Backend | [Backend DEV](https://<DEV_BACKEND_HOST>) |
| DEV redirect | `https://<DEV_FRONTEND_HOST>/redirect.html` |
| Storage | `<STORAGE_ACCOUNT_NAME>`, Brazil South, StorageV2, Standard_LRS |
| Table / container | `OpenThreadWorkspace` / private `attachments` |
| ACA identity | SystemAssigned `<ACA_PRINCIPAL_ID>` |
| Foundry | Existing `openthread-chat`, GPT-4.1 mini `2025-04-14`, GlobalStandard capacity 1 |

## Classificação dos 28 itens

PASS abaixo corresponde à evidência indicada; verificações de configuração ou
Storage por console não substituem os testes de browser autenticado.

| # | Item | Status | Evidência / restante |
| --- | --- | --- | --- |
| 1 | CI automático | PASS | Builds #44 e #46 com reason `individualCI`, após merges normais em develop. |
| 2 | CD automático | PASS | Ambos concluíram ACR push, ACA, SWA, HTTP/config e browser smokes, sem queue manual. |
| 3 | Approval DEV removido | PASS | Approval check 2 removido somente de environment 1 `openthread-dev`; ExclusiveLock check 3 permanece. |
| 4 | Parâmetro manual removido | PASS | YAML sem `enableDevDelivery`; #46 sem template parameters. |
| 5 | Ubuntu fixado | PASS | `ubuntu-24.04`; agente de #44 confirmou Ubuntu 24.04.5. #46 executou o mesmo YAML fixado. |
| 6 | Pipeline final | PASS | #46 succeeded; backend, delivery/pipeline tests, frontend, typecheck, build, Bicep e Docker smoke verdes. |
| 7 | ACA revision | PASS | Revision 0000006 Healthy, active, traffic 100%; digest idêntico ao ACR. |
| 8 | SWA | PASS | Site/bundles/redirect disponíveis; Microsoft button abriu Entra com redirect DEV correto; zero page errors. Login completo pendente. |
| 9 | MI → Table | PASS | SDK no container: create, read, update, stale ETag rejeitado, delete e confirmação de ausência. |
| 10 | MI → Blob | PASS | SDK no container: PNG temporário criado, bytes recuperados, anonimato rejeitado HTTP 409, delete e ausência confirmada. |
| 11 | Conversations persistence | MANUAL TEST REQUIRED | Criar/enviar/reload/logout/login com usuário real e confirmar entidades persistidas. |
| 12 | Memory/context | MANUAL TEST REQUIRED | Frases exatas e pergunta dependente do histórico após reload. |
| 13 | Projects | MANUAL TEST REQUIRED | CRUD, associação, reload e delete preservando conversation. |
| 14 | Pinned | MANUAL TEST REQUIRED | Pin/unpin, reload e logout/login. |
| 15 | Streaming | MANUAL TEST REQUIRED | Chamada real Foundry; deltas progressivos na UI e final persistido. |
| 16 | Stop | MANUAL TEST REQUIRED | Cancelamento real, parcial cancelled, reload e próxima mensagem. |
| 17 | Regenerate | MANUAL TEST REQUIRED | Nova tentativa real, versões anteriores superseded logicamente, reload. |
| 18 | Edit/resend | MANUAL TEST REQUIRED | Replacement e branch lógica consistente após resposta/reload. |
| 19 | Markdown/code | MANUAL TEST REQUIRED | Heading/list/bold/inline/code, highlighting, Copy e ausência de execução HTML. |
| 20 | Multimodal | MANUAL TEST REQUIRED | Preview, upload pela API, inferência real de imagem e retrieval após reload. |
| 21 | Speech-to-text | MANUAL TEST REQUIRED | Chromium expôs SpeechRecognition; permissão, áudio e transcript exigem browser/microfone do usuário. |
| 22 | User isolation | MANUAL TEST REQUIRED | Dois usuários legítimos, incluindo Guest quando disponível; acesso direto indevido deve retornar 404. |
| 23 | Cleanup de conversation | MANUAL TEST REQUIRED | Cleanup do probe Table/Blob passou; cascade explícito de uma conversation real com imagem requer o teste autenticado. |
| 24 | Security | MANUAL TEST REQUIRED | Controles não interativos/configuração abaixo passaram; JWT legítimo e ownership entre usuários aguardam login real. |
| 25 | Logs | PASS | Corte recente de 43 registros de console sem categorias de erro solicitadas. Não certifica todo o histórico de logs. |
| 26 | Custo | PASS | Standard LRS, armazenamento/operações, sem compute dedicado para persistência; estimativa abaixo. |
| 27 | Correções | PASS | CI/CD automático, approval DEV, Ubuntu e default branch corrigidos. Nenhuma feature de produto adicionada. |
| 28 | Blockers restantes | MANUAL TEST REQUIRED | Sessão Microsoft legítima, microfone e segundo usuário para completar os testes de browser. Nenhum blocker cloud pendente. |

PROD: **NOT APPLICABLE**, inexistente nesta fase. Injeção deliberada de falhas em
Storage/RBAC no DEV: **NOT APPLICABLE** nesta execução; falhas parciais e retry de
cleanup permanecem cobertos pelos testes Azurite, sem perturbar o serviço cloud.

## Evidências de delivery, infraestrutura e segurança

[PR #17](https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>/Open%20Thread/_git/Open%20Thread/pullrequest/17)
passou CI #43 e foi concluído por squash. Seu DeliverDev foi **skipped** porque
era PullRequest. O merge produziu #44 automaticamente e entregou DEV com sucesso.
[PR #18](https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>/Open%20Thread/_git/Open%20Thread/pullrequest/18)
passou CI #45 e foi concluído por squash; seu merge produziu #46 automaticamente.
Não houve bypass de policy nem aprovação automática de um check manual.

A pipeline default branch foi alinhada a `refs/heads/develop`: o default anterior
era `main`, que não contém este YAML. A consulta direta por build confirmou que
#44 já havia sido disparada; a listagem de runs inicialmente não a mostrava.
A alteração do default corrige essa inconsistência de configuração, sem atribuir
a ela uma falha de trigger que não foi comprovada.

A etapa de delivery exige CI bem-sucedido, branch develop e evento IndividualCI
ou BatchedCI. PR, feature, main e queue manual não fazem CD. O environment mantém
lock sequencial. O build-validation policy de develop continua enabled e blocking.
CI local: **185 backend + 23 delivery/pipeline = 208 testes**, e **92 frontend**;
typecheck/build, Ruff do teste novo e diff checks passaram. Nove testes novos
cobrem as combinações de branch/evento e falha de CI.

Inventário antes/depois: os mesmos seis recursos — SWA, ACA environment, ACA,
Foundry, ACR e Storage Account. Nenhum recurso novo/duplicado nesta execução.
Deployments atuais Succeeded; nenhum Delete foi solicitado ou ficou pendente.
A rotina usa somente backend.bicep para atualizar o ACA existente, além de
publicar assets no SWA existente; não reaplica bootstrap/Storage nem modifica Entra/Foundry.

A identidade do ACA mantém apenas os assignments constatados: AcrPull no ACR;
Storage Table Data Contributor e Storage Blob Data Contributor na Storage Account.
DefaultAzureCredential confirmou `ManagedIdentityCredential` como credencial
bem-sucedida. Probes usaram partition `TEMP-DEV-VALIDATION-<uuid>` e blob
`temporary-dev-validation/<uuid>.png`; cleanup confirmou ausência de ambos.
Uma inspeção limitada de metadados, sem conteúdo, constatou zero entidades/blobs
de usuário e zero órfãos no momento anterior aos testes manuais.

Controles confirmados no DEV:

- `/health` e `/health/version`: 200; commit/build/digest correspondem à release.
- POST `/api/chat` sem token: 401; GET attachment sem token: 401.
- POST `/api/chat` com body acima de 65536 bytes: 413, sem inferência.
- Preflight SWA origin: 200; origin externo: 400, sem allow-origin externo.
- HTTPS; ingress allowInsecure false; port 8000; minReplicas 0; maxReplicas 2.
- Entra tenant `<AZURE_TENANT_ID>`, audience
  `<ENTRA_API_CLIENT_ID>`, scope `access_as_user` configurados.
- Rate limit 5/60s; concurrency 1 por processo; body 65536 bytes; mensagem 512 bytes.
- Budget 1000, safety margin 100, max completion tokens 256 confirmados no container.
- Container non-root, UID 100. ACR admin disabled. Foundry API key permanece secretRef.
- Storage TLS1.2/HTTPS; Blob public access false; shared-key access false;
  container publicAccess None. Nenhuma account key utilizada/retrieved para runtime.
- Bundle analisado aponta ao backend/redirect DEV; zero padrões de connection
  string/account key/private key. A pipeline fornece apenas configurações públicas VITE.
- JWT validation, ownership, limits e erros sanitizados preservados no código e
  suites; comportamentos autenticados reais aguardam os testes abaixo.

O corte de logs revisado não encontrou Storage 403, Blob/Table errors, Foundry
errors, timeout, startup error ou unhandled exception. Houve timeouts em sondas
HTTP durante a execução; repetições confirmaram health 200 e body excessivo 413.
A causa desses timeouts não foi comprovada. Com minReplicas 0, latência de cold
start deve ser observada, sem alterar escala nesta rodada.
Limits de admissão são locais ao processo; leases/ETags do Table protegem a
conversation entre replicas. Isso não constitui rate limit distribuído global.

## Checklist manual exato

Usar [DEV](https://<DEV_FRONTEND_HOST>), em browser com
microfone. A Foundry quota constatada é **1 RPM / 1000 TPM**: aguardar pelo menos
70 segundos entre inferências, inclusive Regenerate e Edit. Em 429, respeitar
Retry-After. Não copiar tokens, headers Authorization, HAR ou Copy as curl/fetch.
Registrar somente IDs de recursos, status HTTP, horários e resultados não sensíveis.

1. **Login:** entrar com Microsoft como A; confirmar retorno ao app no DEV,
   acesso ao chat e requisições protegidas aceitas. Logout e novo login devem funcionar.
2. **Conversation:** New chat; enviar exatamente `Meu nome é Leandro.`; aguardar
   resposta real. Registrar conversation UUID da resposta/API, sem headers.
   Reload: Recents e mensagens devem permanecer. Logout/login: reabrir o mesmo chat.
3. **Memory:** após a pausa, enviar `Qual é meu nome?`; esperar Leandro. Reload,
   reabrir e, após a próxima pausa, perguntar `Como eu me chamo?`; esperar Leandro.
   Confirmar que o POST envia texto/current conversation_id, sem histórico fornecido
   pelo frontend, e que o GET após reload recupera mensagens da API.
4. **Projects:** criar `DEV E2E project`, renomear, mover o chat para ele, reload
   e confirmar associação. Remover associação; associar novamente; deletar Project.
   O chat e suas mensagens devem sobreviver, sem project_id ativo.
5. **Pins:** pin, reload, logout/login e confirmar pinned; unpin e reload novamente.
6. **Streaming + Markdown:** após a pausa, enviar
   `Use heading, lista, negrito, inline code e bloco Python com print(1). Inclua HTML literal fora do bloco: <img src=x onerror="window.__DEV_E2E_HTML_EXECUTED__=true">.`
   Antes do envio, definir `window.__DEV_E2E_HTML_EXECUTED__ = false` no Console.
   Observar texto progressivo antes do final e eventos SSE delta antes de completed.
   Confirmar formatação/highlighting. Copy do bloco deve colar `print(1)` como texto.
   HTML recebido deve permanecer texto/ser omitido, sem executar scripts/event handlers;
   `window.__DEV_E2E_HTML_EXECUTED__` deve continuar false. Se o modelo não devolver
   esse HTML literal, registrar que essa parte não foi exercitada pelo output real.
   Reload deve conservar a resposta final.
7. **Stop:** após a pausa, pedir `Liste 40 fatos curtos sobre astronomia.`
   Clicar Stop quando os primeiros trechos aparecerem. Confirmar interrupção,
   parcial persistida e status cancelled via API. Reload deve conservar estado
   coerente. Após a pausa, enviar uma mensagem curta e confirmar que o chat funciona.
8. **Regenerate:** após a pausa, regenerar a última resposta concluída. Observar
   streaming; reload deve mostrar a versão ativa correta. A anterior deve ser
   superseded na visão lógica, com histórico preservado.
9. **Edit:** após a pausa, editar a segunda mensagem do usuário para
   `Qual nome informei? Responda apenas o nome.`; reenviar. Esperar Leandro,
   streaming e replacements consistentes. Reload deve manter a nova branch lógica.
   Tentativas posteriores antigas ficam superseded; markers r:/v: podem representar
   essa projeção sem regravar status de cada entidade antiga.
10. **Imagem:** usar [PNG de teste, 604 bytes](validation/dev-multimodal.png):
    fundo azul com círculo amarelo. Selecionar/arrastar, confirmar preview e enviar
    `Descreva as cores e a forma desta imagem.` após a pausa. Esperar descrição
    coerente azul/amarelo/círculo. Upload deve retornar 201, metadados image/png
    e resposta real do deployment openthread-chat. Reload: imagem acessível na UI;
    attachment API autenticada 200, sem token 401, Blob direto anônimo bloqueado.
    Registrar conversation/attachment/message IDs para conferência de metadata/Blob.
11. **Speech:** clicar microfone, permitir acesso, ditar texto curto, finalizar.
    Texto deve aparecer no composer, ser editável e não ser enviado automaticamente.
    Cancelamento/negação devem ter tratamento visual. Sem API suportada, registrar
    NOT APPLICABLE para esse browser, sem atribuir um bug à aplicação.
12. **User B:** usar perfil/browser separado e outro usuário legítimo (Guest se
    disponível). Confirmar identidade diferente e ausência dos chats/projects/pins
    de A. Criar conversation/project de teste de B. Executar os testes de IDs
    indevidos abaixo; esperar 404. Sem segundo usuário, manter item pendente.
13. **Cleanup:** entrar como A e deletar o chat de teste com a imagem. Esperar 204,
    ausência da sidebar/API e remoção de c:/m:/a:/r:/v:/t: associados e Blob prefix.
    Conferir via MI usando apenas os IDs anotados; não usar account keys. Se houver
    falha parcial natural, repetir DELETE/listar conversations como A para retomar
    cleanup. Limpar também os recursos temporários próprios de B como B.

### Requests de ownership sem copiar bearer token

No browser já autenticado de B, usar Console para instalar este wrapper **uma
verificação por vez**. Ele mantém os headers da chamada legítima do próprio app;
não cria tokens, não altera identidade e imprime somente status/presença de bearer.
Usar exclusivamente os recursos temporários de validação de A/B.

```javascript
const backend = "https://<DEV_BACKEND_HOST>";
const fromPath = "/api/conversations/UUID_DE_B";
const toPath = "/api/conversations/UUID_DE_A";
const method = "GET";
const originalFetch = window.fetch.bind(window);
window.restoreOwnershipProbe = () => { window.fetch = originalFetch; };
window.fetch = async (input, init) => {
  const url = new URL(input instanceof Request ? input.url : String(input), location.href);
  const verb = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
  if (url.origin === backend && url.pathname === fromPath && verb === method) {
    window.restoreOwnershipProbe();
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    const bearerPresent = headers.get("Authorization")?.startsWith("Bearer ") === true;
    url.pathname = toPath;
    const response = await originalFetch(input instanceof Request ? new Request(url, input) : url.toString(), init);
    console.info("Ownership result", { status: response.status, bearerPresent });
    return response;
  }
  return originalFetch(input, init);
};
```

Após instalar, selecionar o chat próprio de B (selecionar outro antes, se já
estiver aberto). Sua chamada GET será direcionada ao ID de A, ainda com a sessão
de B: esperar **404 e bearerPresent true**. Restaurar com
`window.restoreOwnershipProbe()` ou reload entre verificações.

Repetir GET usando toPath `/api/conversations/UUID_DE_A/attachments/ATTACHMENT_DE_A`
e o mesmo fromPath de conversation própria B: esperar 404, sem bytes de A.
Para Project, usar fromPath `/api/projects/PROJECT_DE_B`, toPath com PROJECT_DE_A,
method PATCH, e acionar rename do Project próprio B. Para alteração de chat, usar
os conversation paths com method PATCH e acionar pin/unpin de B. Para delete,
method DELETE e deletar o chat de teste próprio B. Todos devem retornar 404;
qualquer sucesso indevido é FAIL e exige diagnóstico. Não exportar headers/token.

## Custo e limitações

Storage Standard LRS não possui servidor de banco/compute dedicado. Para até
1 GB Table + 1 GB Blob Hot e aproximadamente 10 mil reads/writes por serviço/mês,
espera-se ordem de **US$ 0,10–US$ 1/mês** de persistência. É estimativa, não preço
fixo; tráfego, impostos/contrato e serviços já existentes ficam fora desse valor.
Volume constatado antes dos testes manuais: zero entidades/blobs de usuário.
[Table pricing](https://azure.microsoft.com/en-us/pricing/details/storage/tables/),
[Blob pricing](https://azure.microsoft.com/en-us/pricing/details/storage/blobs/).

Sem novas features, modelos, recursos Azure, bancos relacionais ou alterações
Entra/Foundry. Este relatório e a imagem de teste são artefatos locais gerados após
o deploy; as mudanças de pipeline/documentação de delivery foram publicadas pelos PRs.

**Open Thread DEV cloud delivery and non-interactive E2E validation completed successfully.**
