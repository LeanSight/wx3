python wx3.py diarize   --hf-token  %HF_TOKEN% c:\workspace\@recordings\mini-obeya2.mp4
python wx3.py transcribe  c:\workspace\@recordings\mini-obeya2.mp4 
python wx3.py process   --hf-token  %HF_TOKEN% c:\workspace\@recordings\mini-obeya2.mp4 --speaker-names "Guy,Jim"
REM python wx3.py process   --hf-token  %HF_TOKEN% "c:\workspace\@recordings\20250417 23people Fundamentos de Kanban\Ordenado\*.mp4"