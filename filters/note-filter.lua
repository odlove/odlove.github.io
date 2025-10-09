-- Lua filter to add class="note" to quote blocks that should be styled as notes
-- Usage in LaTeX: wrap content in \begin{quote}...\end{quote}

function Div(el)
  -- Check if this is a quote block
  if el.classes:includes("quote") then
    -- Add "note" class to quote blocks
    -- You can add more logic here if needed to distinguish regular quotes from notes
    el.classes:insert("note")
  end
  return el
end
