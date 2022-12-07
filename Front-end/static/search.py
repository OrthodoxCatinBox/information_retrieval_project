from flask import Flask, url_for
from flask import request
from flask import render_template

app=Flask(__name__,static_url_path='/static')

Data=[
    {'title':'标题1','introduction':'简介1','date':'日期1'},
    {'title':'标题2','introduction':'简介2','date':'日期2'},
    {'title':'标题3','introduction':'简介3','date':'日期3'},
]
HITS=len(Data)

@app.route('/')
def search():
    return render_template('search.html')

#app.run()

@app.route('/result',methods=['get'])
def result():
    keywords = request.args.get('keywords')
    '''
        这部分把keyword放入elasticsearch中，然后得到下面的Data和HITS
    '''
    Data = [
        {'title': '标题1', 'introduction': '简介1', 'date': '日期1'},
        {'title': '标题2', 'introduction': '简介2', 'date': '日期2'},
        {'title': '标题3', 'introduction': '简介3', 'date': '日期3'},
    ]
    HITS = len(Data)
    return render_template('result.html',HITS=HITS,Data=Data,keywords=keywords)

app.run()
#if __name__=='__main__':
#    app.run()