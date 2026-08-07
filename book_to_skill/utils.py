*** Begin Patch
*** Update File: book_to_skill/utils.py
@@
     if ext == ".pdf":
         print(f"Extracting PDF: {input_str}")
-        if extraction_mode == "technical":
-            print("Mode: technical — using Docling (layout-aware)...", end=" ", flush=True)
-            text = extract_with_docling(input_str)
-            if text:
-                method = "docling"
-                print("OK")
-            else:
-                print("not available, falling back to pdftotext")
-                extraction_mode = "text"
+        # Try Firecrawl anydoc first (if available) — works across many formats
+        try:
+            print("Trying Firecrawl anydoc extractor...", end=" ", flush=True)
+            anydoc_text, anydoc_method = extract_with_anydoc(input_str)
+            if anydoc_text:
+                text = anydoc_text
+                method = anydoc_method
+                print("OK")
+            else:
+                print("no output")
+        except Exception as exc:
+            # anydoc not available or failed; continue with other extractors
+            print("not available or failed:", str(exc))
+
+        if not text and extraction_mode == "technical":
+            print("Mode: technical — using Docling (layout-aware)...", end=" ", flush=True)
+            text = extract_with_docling(input_str)
+            if text:
+                method = "docling"
+                print("OK")
+            else:
+                print("not available, falling back to pdftotext")
+                extraction_mode = "text"
*** End Patch
