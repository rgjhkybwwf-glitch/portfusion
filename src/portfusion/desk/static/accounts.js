/* ACCOUNTS: the page's draw. */

Object.assign(DRAW, {
  /* ACCOUNTS — the register, the money that crossed each account's boundary, and the year's
     income and costs. The engine's tables, drawn as they come.

     THE YEAR'S INCOME IS ONE LINE PER ACCOUNT, the book first, each category a sum of money;
     an account's own rows open beneath its line, as a quarter's detail does on Performance. */
  accounts(d) {
    const asMoney = Object.fromEntries([...d.categories, "total"].map((c) =>
      [c, (r) => cell("amount", r[c])]));
    /* A FOREIGN ROW'S CONVERSION, and nothing on a sterling one: the amount at its currency's
       places, as a local price is printed. */
    const paid = (draw) => (r) => r.currency ? draw(r) : "<td></td>";
    const conversion = { currency: paid((r) => cell("currency", r.currency)),
                         local_amount: paid((r) => `<td class="num">${localPrice(r.local_amount, r.currency)}</td>`),
                         rate_date: paid((r) => cell("rate_date", r.rate_date)) };
    return page({
      scope: "who each account is, and the money that crossed its boundary",
      work: `<h2>Register</h2>${table(d.register, d.columns.register, "", () => "",
          { name: "register", cells: { feed_key: (r) => cell("feed_key", r.feed_key || "") } })}
        <h2>External capital</h2>${table(d.movements, d.columns.movements, "", () => "", { name: "capital" })}
        <h2>Income and costs, ${esc(d.year)}</h2>${table(d.income, d.columns.summary, "", () => "",
          { sort: false, cells: asMoney,
            afterRow: (r, span) => detailRow(r.rows.length
              ? table(r.rows, r.columns, "", () => "", { name: r.account, cells: conversion }) : "", span) })}`,
    });
  },
});
