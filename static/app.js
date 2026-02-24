/* Portal CISP - JS */
(function () {
  const $ = (id) => document.getElementById(id);

  const toastEl = $("appToast");
  const toast = toastEl ? new bootstrap.Toast(toastEl, { delay: 3500 }) : null;

  const fmt = {
    moeda(v) {
      if (v == null || v === "") return "-";
      try { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v); }
      catch { return String(v); }
    },
    numero(v) {
      if (v == null || v === "") return "-";
      try { return new Intl.NumberFormat("pt-BR").format(v); }
      catch { return String(v); }
    },
    data(v) {
      if (!v) return "-";
      try { return new Date(v).toLocaleString("pt-BR"); }
      catch { return String(v); }
    },
  };

  const PBI_URL = "https://app.powerbi.com/reportEmbed?reportId=ccd6bbdb-151f-4c60-a39e-885fae091abf&appId=1ada0eb7-865f-4145-8c42-83942212adc0&autoAuth=true&ctid=b3cf12b1-e192-40d4-a26e-bacee6c0fa4e";

  function notify(msg) {
    if (!$("toastBody") || !toast) return;
    $("toastBody").textContent = msg;
    $("toastTime").textContent = "agora";
    toast.show();
  }

  function setStatus(kind, text) {
    const badge = $("statusBadge");
    const status = $("statusText");
    if (!badge || !status) return;

    badge.className = "badge";
    const map = {
      idle: "text-bg-light border",
      ok: "text-bg-success",
      warn: "text-bg-warning",
      err: "text-bg-danger",
      work: "text-bg-primary",
    };
    badge.classList.add(...(map[kind] || map.idle).split(" "));
    badge.textContent = kind === "idle" ? "Aguardando" :
                       kind === "work" ? "Processando" :
                       kind === "ok" ? "Pronto" :
                       kind === "warn" ? "Atenção" : "Erro";
    status.textContent = text || "";
  }

  function digitsOnly(s) {
    return (s || "").replace(/\D+/g, "");
  }

  function normalizarRaiz(input) {
    const d = digitsOnly(input);
    if (d.length >= 8) return d.slice(0, 8);
    return d;
  }

  async function apiHealth() {
    try {
      const r = await fetch("/api/health");
      const b = $("healthBadge");
      if (r.ok) {
        if (b) b.className = "badge text-bg-success";
      } else {
        if (b) b.className = "badge text-bg-danger";
      }
    } catch {
      const b = $("healthBadge");
      if (b) b.className = "badge text-bg-danger";
    }
  }

  async function sincronizar(raiz) {
    const r = await fetch(`/api/sincronizar/${raiz}`);
    if (!r.ok) {
      let msg = "Falha ao sincronizar";
      try { const j = await r.json(); msg = j.mensagem || msg; } catch {}
      throw new Error(msg);
    }
    return true;
  }

  async function obter(raiz) {
    const r = await fetch(`/api/cliente/${raiz}`);
    const j = await r.json();
    if (!r.ok || !j.success) {
      throw new Error(j.erro || "Falha ao obter dados");
    }
    return j;
  }

  function clearLists() {
    $("tblRestritivas").innerHTML = "";
    $("tblConsultas").innerHTML = "";
    $("listAssocCons").innerHTML = "";
    $("listAssocNao").innerHTML = "";
    $("tblRating").innerHTML = "";
    const segAcc = $("segAccordion"); if (segAcc) segAcc.innerHTML = "";

    $("restritivasEmpty").classList.add("d-none");
    $("consultasEmpty").classList.add("d-none");
    $("assocConsEmpty").classList.add("d-none");
    $("assocNaoEmpty").classList.add("d-none");
    $("ratingEmpty").classList.add("d-none");
    const segEmpty = $("segEmpty"); if (segEmpty) segEmpty.classList.add("d-none");
  }

  function showEmptyState() {
    $("clienteEmpty").classList.remove("d-none");
    $("clienteBox").classList.add("d-none");
    $("btnBaixarJson").classList.add("d-none");
    $("btnLimpar").classList.add("d-none");
    $("atualizacao").textContent = "";
    clearLists();

    $("mRating").textContent = "-";
    $("mRatingDesc").textContent = "";
    $("mDebito").textContent = "-";
    $("mLimite").textContent = "-";
    $("mAcumulo").textContent = "-";
    $("mVencidos").textContent = "-";
  }

  function render(data) {
    const p = data.principal || null;
    if (!p) {
      showEmptyState();
      setStatus("warn", "Nenhum dado encontrado no Postgres para esta raiz.");
      return;
    }

    $("clienteEmpty").classList.add("d-none");
    $("clienteBox").classList.remove("d-none");
    $("btnBaixarJson").classList.remove("d-none");
    $("btnLimpar").classList.remove("d-none");

    $("razaoSocial").textContent = p.razao_social || "-";
    $("nomeFantasia").textContent = p.nome_fantasia || "-";
    $("cnpj").textContent = p.cnpj || "-";
    $("situacaoRF").textContent = p.situacao_receita_federal || "-";
    $("cnae").textContent = p.cnae || "-";
    $("atividade").textContent = p.descricao_atividade_fiscal || "-";
    $("dataFundacao").textContent = fmt.data(p.data_fundacao);
    $("dataInclusaoCISP").textContent = fmt.data(p.data_inclusao_cisp);
    $("modificadoEm").textContent = fmt.data(p.data_atualizacao);
    $("horaModificacao").textContent = p.hora_modificacao || "-";
    $("usuarioModificacao").textContent = p.usuario_modificacao || "-";

    const addr = [p.endereco, p.bairro, p.cidade, p.uf, p.cep].filter(Boolean).join(", ");
    $("endereco").textContent = addr || "-";

    $("atualizacao").textContent = p.data_atualizacao ? `Atualizado em ${fmt.data(p.data_atualizacao)}` : "";

    // Metrics
    $("mRating").textContent = p.rating_atual || "-";
    $("mRatingDesc").textContent = p.descricao_rating || "";
    $("mDebito").textContent = fmt.moeda(p.total_debito_atual);
    $("mLimite").textContent = fmt.moeda(p.total_limite_credito);
    $("mAcumulo").textContent = fmt.moeda(p.total_maior_acumulo);
    $("mVencidos").textContent = `${fmt.moeda(p.total_debito_vencido_05_dias)} / ${fmt.moeda(p.total_debito_vencido_15_dias)} / ${fmt.moeda(p.total_debito_vencido_30_dias)}`;
    $("mDataAcumulo").textContent = fmt.data(p.data_maior_acumulo);
    $("mUltimaCompra").textContent = fmt.data(p.data_ultima_compra);
    $("mAssocUltimaCompra").textContent = p.codigo_associada_ultima_compra ? `Associada ${p.codigo_associada_ultima_compra}` : "";
    $("mAssoc2m").textContent = fmt.numero(p.qtd_associadas_vendas_ultimos_2meses);
    $("mSintegra").textContent = p.situacao_sintegra || "-";

    clearLists();

    // Restritivas
    const restr = (data.restritivas || []).slice(0, 200);
    if (!restr.length) {
      $("restritivasEmpty").classList.remove("d-none");
    } else {
      $("tblRestritivas").innerHTML = restr.map(r => `
        <tr>
          <td>${escapeHtml(r.descricao_primeira_restritiva || "-")}</td>
          <td class="text-nowrap">${escapeHtml((r.data_ocorrencia || "").split("T")[0] || "-")}</td>
          <td>${escapeHtml(r.razao_social || "-")}</td>
        </tr>
      `).join("");
    }

    // Positivas por segmento
    const segs = (data.positivaSegmentos || []).slice(0, 50);
    if (!segs.length) {
      const segEmpty = $("segEmpty"); if (segEmpty) segEmpty.classList.remove("d-none");
    } else {
      const acc = $("segAccordion");
      if (acc) {
        acc.innerHTML = segs.map((s, i) => {
          const pid = `seg-${i}`;
          const itens = (s.positivas || []).slice(0, 200).map(p => `
            <tr>
              <td class="text-nowrap">${escapeHtml((p.dataUltimaCompra || "").split("T")[0] || "-")}</td>
              <td class="text-nowrap">${escapeHtml((p.dataMaiorAcumulo || "").split("T")[0] || "-")}</td>
              <td class="text-end">${escapeHtml(String(fmt.moeda(p.valorMaiorAcumulo)))}</td>
              <td>${escapeHtml(p.razaoSocial || "-")}</td>
              <td class="text-end">${escapeHtml(String(fmt.moeda(p.valorDebitoAtual)))}</td>
              <td class="text-end">${escapeHtml(String(fmt.moeda(p.valorLimiteCredito)))}</td>
            </tr>
          `).join("");
          const table = `
            <div class="table-responsive">
              <table class="table table-sm align-middle">
                <thead>
                  <tr>
                    <th class="text-nowrap">Última compra</th>
                    <th class="text-nowrap">Maior acúmulo</th>
                    <th class="text-end">Valor acumulo</th>
                    <th>Associada</th>
                    <th class="text-end">Débito atual</th>
                    <th class="text-end">Limite crédito</th>
                  </tr>
                </thead>
                <tbody>${itens}</tbody>
              </table>
            </div>
          `;
          return `
            <div class="accordion-item">
              <h2 class="accordion-header" id="h-${pid}">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#c-${pid}" aria-expanded="false" aria-controls="c-${pid}">
                  ${escapeHtml(s.descricaoSegmento || "-")} • Assoc: ${fmt.numero(s.totalAssociadasSegmento)} • Débito: ${fmt.moeda(s.valorTotalDebitoSegmento)}
                </button>
              </h2>
              <div id="c-${pid}" class="accordion-collapse collapse" aria-labelledby="h-${pid}" data-bs-parent="#segAccordion">
                <div class="accordion-body">
                  ${table}
                </div>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    // Consultas
    const cons = (data.consultas_mensais || []).slice(0, 200);
    if (!cons.length) {
      $("consultasEmpty").classList.remove("d-none");
    } else {
      $("tblConsultas").innerHTML = cons.map(c => `
        <tr>
          <td>${escapeHtml(c.mes_ano || "-")}</td>
          <td class="text-end">${escapeHtml(String(fmt.numero(c.quantidade_consultas)))}</td>
        </tr>
      `).join("");
    }

    // Associadas
    const ac = (data.associadas_consultaram || []).slice(0, 200);
    if (!ac.length) {
      $("assocConsEmpty").classList.remove("d-none");
    } else {
      $("listAssocCons").innerHTML = ac.map(x => `<li class="list-group-item">${escapeHtml(x.razao_social || "-")}</li>`).join("");
    }

    const an = (data.associadas_nao_concederam || []).slice(0, 200);
    if (!an.length) {
      $("assocNaoEmpty").classList.remove("d-none");
    } else {
      $("listAssocNao").innerHTML = an.map(x => `<li class="list-group-item">${escapeHtml(x.razao_social || "-")}</li>`).join("");
    }
    const ex = data.extras || {};
    $("mCheques").textContent = fmt.numero(ex.tot_cheques_sem_fundo);
    $("mProtesto").textContent = fmt.numero(ex.tot_titulos_protesto);

    // Rating (histórico/análises)
    const ratings = (data.ratings || []).slice(0, 200);
    if (!ratings.length) {
      $("ratingEmpty").classList.remove("d-none");
    } else {
      $("tblRating").innerHTML = ratings.map(r => `
        <tr>
          <td class="text-nowrap">${escapeHtml((r.data || "").split("T")[0] || "-")}</td>
          <td>${escapeHtml(r.classificacao || "-")}</td>
          <td>${escapeHtml(r.descricaoClassificacao || "-")}</td>
        </tr>
      `).join("");
    }
  }

  // Minimal HTML escaping
  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setLoading(isLoading, label) {
    $("btnBuscar").disabled = isLoading;
    const sp = $("spBuscar");
    if (sp) sp.classList.toggle("d-none", !isLoading);
    if (isLoading) setStatus("work", label || "");
  }

  function addChip(raiz) {
    const key = "cisp_recent_roots";
    const prev = JSON.parse(localStorage.getItem(key) || "[]");
    const next = [raiz, ...prev.filter(x => x !== raiz)].slice(0, 10);
    localStorage.setItem(key, JSON.stringify(next));
    renderChips();
  }

  function renderChips() {
    const key = "cisp_recent_roots";
    const list = JSON.parse(localStorage.getItem(key) || "[]");
    const chips = $("chips");
    if (!chips) return;

    if (!list.length) {
      $("chipsEmpty").classList.remove("d-none");
      chips.innerHTML = "";
      return;
    }
    $("chipsEmpty").classList.add("d-none");
    chips.innerHTML = list.map(r => `
      <button type="button" class="btn btn-sm btn-outline-secondary" data-root="${r}">${r}</button>
    `).join("");

    [...chips.querySelectorAll("button[data-root]")].forEach(btn => {
      btn.addEventListener("click", () => {
        $("raiz").value = btn.getAttribute("data-root") || "";
        buscarSomente();
      });
    });
  }

  async function buscarSomente() {
    const raiz = normalizarRaiz($("raiz").value);
    $("raiz").value = raiz;
    if (!/^\d{8}$/.test(raiz)) {
      setStatus("warn", "Informe a raiz (8 dígitos) ou cole o CNPJ completo.");
      notify("Raiz inválida.");
      return;
    }

    setLoading(true, "Consultando no Postgres...");
    try {
      let data = await obter(raiz);
      const p = data.principal || {};
      const vazio = !p.razao_social && !p.cnpj && !p.nome_fantasia && !p.cidade && !p.uf;
      if (vazio) {
        setStatus("work", "Buscando na API CISP...");
        try {
          await sincronizar(raiz);
          data = await obter(raiz);
        } catch (e) {
          // mantém data original se API não retornar
        }
      }
      render(data);
      addChip(raiz);
      const p2 = data.principal || {};
      const vazio2 = !p2.razao_social && !p2.cnpj && !p2.nome_fantasia && !p2.cidade && !p2.uf;
      if (vazio2) {
        setStatus("warn", "Sem dados para esta raiz no Postgres/API.");
      } else {
        setStatus("ok", "Consulta concluída.");
      }
    } catch (e) {
      showEmptyState();
      setStatus("err", e.message || "Erro na consulta.");
      notify(e.message || "Erro na consulta.");
    } finally {
      setLoading(false);
    }
  }

  // atualizarEConsultar removido

  function downloadJson(obj, raiz) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cisp_${raiz || "resultado"}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // Theme toggle
  function toggleTheme() {
    const html = document.documentElement;
    const cur = html.getAttribute("data-bs-theme") || "light";
    const next = cur === "light" ? "dark" : "light";
    html.setAttribute("data-bs-theme", next);
    localStorage.setItem("cisp_theme", next);
  }

  function initTheme() {
    const saved = localStorage.getItem("cisp_theme");
    if (saved) document.documentElement.setAttribute("data-bs-theme", saved);
  }

  // Wire up
  function init() {
    initTheme();
    apiHealth();
    renderChips();
    showEmptyState();

    const pbi = $("pbiFrame");
    if (pbi) pbi.src = PBI_URL;

    $("raiz").addEventListener("input", (e) => {
      // deixa só números enquanto digita
      e.target.value = digitsOnly(e.target.value).slice(0, 14);
    });

    $("raiz").addEventListener("keydown", (e) => {
      if (e.key === "Enter") buscarSomente();
    });

    $("btnBuscar").addEventListener("click", buscarSomente);
    // botão de atualizar removido; apenas consultar

    $("btnLimpar").addEventListener("click", () => {
      $("raiz").value = "";
      showEmptyState();
      setStatus("idle", "Aguardando consulta");
    });

    $("btnBaixarJson").addEventListener("click", async () => {
      const raiz = normalizarRaiz($("raiz").value);
      try {
        const data = await obter(raiz);
        downloadJson(data, raiz);
      } catch (e) {
        notify("Não foi possível baixar o JSON.");
      }
    });

    $("themeBtn").addEventListener("click", toggleTheme);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
