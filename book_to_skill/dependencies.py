*** Begin Patch
*** Update File: book_to_skill/dependencies.py
@@
     {
         "label": "RTF",
         "modules": ["striprtf"],
         "any_of_modules": True,
         "system": [],
         "note": "falls back to a basic regex cleanup if missing",
     },
+    {
+        "label": "AnyDoc (Firecrawl)",
+        "modules": [],
+        "any_of_modules": True,
+        "any_tool_suffices": True,
+        "system": [
+            ("node", "Node.js", "Install Node.js: https://nodejs.org/"),
+            ("npx", "npx", "Install npm / npx (comes with Node.js)")
+        ],
+        "note": "Optional unified parser: install @firecrawl/anydoc (npm i -g @firecrawl/anydoc) or use npx",
+    },
*** End Patch
