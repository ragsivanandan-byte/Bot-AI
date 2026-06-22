"use strict";
// Logique de simulation pure (sans DOM) — partagée navigateur + Node.
// Port fidèle de simulate()/weekly_dividend_per_share() de strc_dca.py.
(function (global) {
  function weeklyDividendPerShare(weekISO, schedule, fallbackApy, par) {
    if (schedule && schedule.length) {
      let monthly = schedule[0].amount_per_share; // défaut si rien <= semaine
      for (const s of schedule) {
        if (s.ex_date <= weekISO) monthly = s.amount_per_share;
        else break; // schedule trié par date croissante
      }
      return (monthly * 12) / 52;
    }
    return (par * fallbackApy) / 52;
  }

  function simulate(closes, weekly, mode, schedule, apy, reinvest, par) {
    let shares = 0, invested = 0, divCash = 0, divReinv = 0;
    const history = [];
    for (const pt of closes) {
      const buy = mode === "par" ? par : pt.close;
      const mark = buy;
      const dps = weeklyDividendPerShare(pt.date, schedule, apy, par);
      const divWeek = shares * dps;
      if (reinvest) {
        shares += buy > 0 ? divWeek / buy : 0;
        divReinv += divWeek;
      } else {
        divCash += divWeek;
      }
      const newShares = buy > 0 ? weekly / buy : 0;
      shares += newShares;
      invested += weekly;
      history.push({ date: pt.date, close: pt.close, estimated: pt.estimated, invested, shares, value: shares * mark });
    }
    const latest = closes.length ? closes[closes.length - 1].close : 0;
    const finalMark = mode === "par" ? par : latest;
    const marketValue = shares * finalMark;
    const totalDiv = divCash + divReinv;
    return {
      mode, invested, shares,
      avgCost: shares ? invested / shares : 0,
      latestClose: finalMark,
      marketValue,
      dividends: totalDiv,
      dividendsCash: divCash,
      dividendsReinvested: divReinv,
      capitalPL: marketValue - invested,
      capitalPLpct: invested ? ((marketValue - invested) / invested) * 100 : 0,
      totalValue: marketValue + divCash,
      totalPL: marketValue + divCash - invested,
      totalPLpct: invested ? ((marketValue + divCash - invested) / invested) * 100 : 0,
      yieldOnCost: invested ? (totalDiv / invested) * 100 : 0,
      history,
    };
  }

  const api = { weeklyDividendPerShare, simulate };
  global.STRCsim = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
