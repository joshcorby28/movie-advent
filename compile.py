import shutil

shutil.copy('scss/main.scss', 'static/main.css')
print("Compiled SCSS to CSS")