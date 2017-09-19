# coding: UTF-8
import ecell, ecell.emc, ecell.Session, ecell.ecs
import os,sys
import numpy as np 
import csv                       
import json
import collections
import matplotlib 
matplotlib.use("Agg") 
import matplotlib.pyplot as plt 
import seaborn as sns
import copy

template = {'legend.numpoints': 1, 'axes.axisbelow': True, 'axes.labelcolor': '.15', 'ytick.major.size': 4.0, 'axes.grid': False, 'ytick.minor.size': 0.0, 'legend.scatterpoints': 1, 'axes.edgecolor': "black", 'grid.color': 'white', 'legend.frameon': False, 'ytick.color': '.15', 'xtick.major.size': 4.0, 'figure.facecolor': "#EAEAF2", 'xtick.color': '.15', 'xtick.minor.size': 3.0, 'xtick.direction': u'out', 'lines.solid_capstyle': u'round', 'grid.linestyle': u'-', 'image.cmap': u'Greys', 'axes.facecolor': "white", 'text.color': '.15', 'ytick.direction': u'out', 'axes.linewidth': 1.0,'xtick.major.width': 1.0, 'ytick.major.width': 1.0,}
sns.set(font = "Helvetica")
sns.set_context("poster", font_scale=1.2, rc={"lines.linewidth": 1.0})
sns.set_style(template)
sns.set_palette("colorblind")

class EX:
    def __init__( self, aSession ):
        self.aSession        = aSession
        self.EntitytypeList  = [ 'System','Process','Variable' ]
        self.treeDict        = None 
        self.treeDictKeys    = []
        self.PropertyList    = ['','Activity','Value']
        self.LoggerList      = []       
        self.saveEntityDict  = {}  
        self.saveStepperDict = {} 
        self.updatableList   = []
        self.updatableStubs  = []
        self.treeJson        = collections.OrderedDict() 

    def getAllEntityList( self,SystemPath ): 
        '''
        任意のSystem直下のEntity(System, Process, Variable)のlistを返す関数。まぁこいつ自身にあまり使い道がない。
        '''
        allEntityList  = [ SystemPath,[] ]    
        for i in range( len( self.EntitytypeList ) ):
            allEntityList[1].append( list( self.aSession.getEntityList( self.EntitytypeList[i],SystemPath ) ) )
            for j in range( len( allEntityList[1][i] ) ):
                allEntityList[1][i][j] = self.EntitytypeList[i] + ':' + SystemPath + ':' + allEntityList[1][i][j]     
        return allEntityList  


    def treeDictionary( self,SystemPath="/" ):
        '''
        ECell3の階層構造をtraceすることで任意のSytem下のモデル構造をdictとして取得する。System Pathをkey、そのSystem直下のEnitityのlistをValueに持つdictを返す。
        '''
        FE = self.getAllEntityList( SystemPath )  #First element
        self.treeDict = []
        self.treeDict.append( FE )
        SystemList = FE[1][0]
        self.treeDictKeys.append( FE[0] ) 
        for i in xrange( len( SystemList ) ):
            SystemList[i] = SystemList[i].replace( ':','' )
            SystemList[i] = SystemList[i].replace( 'System','' )
            self.treeDictKeys.append( SystemList[i] )
        
        while len( SystemList ) > 0:
            Next_SystemList = []
            for i in xrange( len( SystemList ) ) :
                NE = self.getAllEntityList( SystemList[i] ) #Next element
                self.treeDict.append( NE )
                
                for j in xrange( len( NE[1][0] ) ):
                    Next_SystemList.append( NE[1][0][j] )
                    length = len( Next_SystemList ) - 1 
                    Next_SystemList[ length ] = Next_SystemList[ length ].split(':')

                    Next_SystemList[ length ] = Next_SystemList[ length ][1]  + '/' + Next_SystemList[ length ][2]
                    self.treeDictKeys.append( Next_SystemList[ length ] )

            SystemList = Next_SystemList

        self.treeDict = collections.OrderedDict( self.treeDict )      
       
    
    def createAllLogger( self ):
        """
        treeDictionary methodの返り値を利用して、モデル内の全てのVariableとProcessのLoggerを作成。
        """
        for key in self.treeDictKeys:
            properties = self.treeDict[ key ]
            for j in range( 1,3 ):
                for path in properties[j]:
                    FullPN = path + ':' + self.PropertyList[j]
                    aLogger = self.aSession.createLoggerStub( FullPN )
                    aLogger.create()
                    #aLogger.setLoggerpolicy([a,b,c,d])
                    self.LoggerList.append( aLogger )
    
    def createAllLogger2( self ):
        """
        VariableReferenceListを参照して、モデル内で値が変化するはずのないVariableをのぞいた全てのVariable, ProcessのLoggerを作成する。
        """
        LoggereFullPNList = [] 
        for key in self.treeDictKeys:
            for path in self.treeDict[ key ][ 1 ]:   
                #print path
                aEntity = self.aSession.createEntityStub( path )

                if "Flux" in aEntity.getClassname():
                    FullPN = path + ":" + self.PropertyList[ 1 ]
                    aLogger = self.aSession.createLoggerStub( FullPN )
                    aLogger.create() 
                    LoggereFullPNList.append( FullPN )
                    self.LoggerList.append( aLogger)

                VRL = aEntity['VariableReferenceList']
                for VR in VRL:
                    if VR[ 2 ] != 0:
                        FullPN = self.EntitytypeList[ 2 ] + VR[ 1 ] + ":" + self.PropertyList[ 2 ]
                        if FullPN in LoggereFullPNList:
                            pass 
                        else:
                            aLogger = self.aSession.createLoggerStub( FullPN )
                            aLogger.create()
                            LoggereFullPNList.append( FullPN )
                            self.LoggerList.append( aLogger )

    def analysisCoEfficient( self ):
         for key in self.treeDictKeys:
            for path in self.treeDict[ key ][ 1 ]:   
                #print path
                aEntity = self.aSession.createEntityStub( path )

                if "Flux" in aEntity.getClassname():
                    self.updatableList.append( path )
                VRL = aEntity['VariableReferenceList']
                for VR in VRL:
                    if VR[ 2 ] != 0:
                        FullPN = self.EntitytypeList[ 2 ] + VR[ 1 ]
                        if FullPN in self.updatableList:
                            pass 
                        else:
                            self.updatableList.append( FullPN )

    def saveCSV( self,saveDir,args ):#args = [FullPN, StartTime, EndTime, interval]
        """
        ECDじゃなくてCSV形式で保存してくれるよ！
        """
        if len(args) == 1:
            Log = self.aSession.theSimulator.getLoggerData( args[0] )
        if len(args) == 2:
            args.append( self.aSession.getCurrentTime() )
            Log = self.aSession.theSimulator.getLoggerData( args[0], args[1], args[2] ) 
        if len(args) == 3:
            Log = self.aSession.theSimulator.getLoggerData( args[0], args[1], args[2] )
        if len(args) == 4:
            Log = self.aSession.theSimulator.getLoggerData( args[0], args[1], args[2],args[3] )                                     
        FullPN = args[0]
        Data  = np.matrix(Log)
        Data  = Data[:,0]
        Data  = Data.tolist()
        rabelrows = [ 'time', FullPN ]
        for i in range( len(Data) ):
            Data[i].append(Log[i][1])
        Data.insert(0,rabelrows) 
        FullPN   = FullPN.replace('/','_') 
        filename = FullPN + '.csv'
        csvfile  = open( saveDir + "/" + filename,'w')
        writer   = csv.writer(csvfile)
        writer.writerows(Data)
        csvfile.close()

    def createNewLogger( self, ID, name ):
        """
        これはね.......。一度作成したけど意味があるかはわからない。一時的なLoggerを作成するためのmethod
        """
        IDStub = self.aSession.createEntityStub( "Variable:" + ID ) 
        P = self.aSession.theSimulator.createEntity( "ExpressionAssignmentProcess", "Process:" + ID + name )
        V = self.aSession.theSimulator.createEntity( "Variable","Variable:" + ID + name )
        V.Value = IDStub[ "Value" ]
        P.StepperID = "PSV"
        P.VariableReferenceList = [ [ "CP",":" + ID + name, "1" ],[ "Origin",":" + ID, "0" ] ]
        P.Expression = "Origin.Value"
        L = self.aSession.createLoggerStub( "Variable:" + ID + name + ":Value" ) 
        L.create() 
        return L 
    
    def deleteNewLogger( self, ID, name ):
        """
        一時的に作ったLoggerを消去するためのスクリプト
        """
        self.aSession.theSimulator.deleteEntity( "Process:" + ID + name )
        self.aSession.theSimulator.deleteEntity( "Variable:" + ID + name ) 
        
    def saveAllCSV( self,filename,StartTime,EndTime,Interval ): 
        """
        現在作られている全てのLoggerのデータをCSV形式に変換して保存する。
        """
        for a in range( len( self.LoggerList ) ):
            Data      = self.LoggerList[a].getData( StartTime, EndTime, Interval )  
            if len( Data ) > 2:
                break
        Data      = np.matrix(Data)
        Data      = Data[:,0]
        Data      = Data.tolist()
        rabelrows = ['time']
        shortrabelrows = ['time']

        for i in range( a, len( self.LoggerList ) ):
            Next_Data  = self.LoggerList[i].getData( StartTime, EndTime, Interval )
            rabel      = self.LoggerList[i].getName()
            if len(Next_Data) < len(Data):
                print len( Data )
                pass 
            else:
                for j in range(len(Data)):
                    Data[j].append(Next_Data[j][1])
                rabelrows.append( rabel ) 
                #rabel = rabel.split(':')
                #path  = rabel[0][0] + ':' + rabel[1] + ':' + rabel[2]
                #rabel[1] = rabel[1].split('/')
                #rabel[1][-1] = rabel[1][-1].replace(':','')
                #shortrabel = rabel[0][0] + '_' + rabel[1][-1] +':' + rabel[2]
                #shortrabelrows.append(shortrabel)

        Data.insert(0,rabelrows)
        csvfile  = open(filename,'w')
        writer   = csv.writer(csvfile)
        writer.writerows(Data)
        csvfile.close() 

    def graphAll( self, csvfile, imgDir ):
        """
        保存したcsvを読み込んで、グラフ化
        """
        header = open( csvfile, "r" ).readline().rstrip().split(",")  
        Data = np.loadtxt( csvfile, delimiter = ",", skiprows = 1 )  
        if imgDir not in os.listdir("."): 
            os.mkdir(imgDir) 

        for i in range( len( header ) - 1 ):
            fig = plt.figure( figsize = (6,2) )  
            ax  = fig.add_subplot(111)
            ax.plot( Data[:,0], Data[:,i + 1 ] ) 
            ax.grid('on')
            ax.tick_params(top="off")
            ax.tick_params(right="off")
            ax.tick_params(labelsize = 14)
            ax.set_xlabel("Time", fontsize=14 ) 
            ax.set_ylabel( header[ i + 1 ].split(':')[-2].split('/')[-1], fontsize=14 ) 
            saveName = header[ i + 1 ].replace("/","|")
            saveName = saveName.replace(":","_")
            fig.savefig( "./" + imgDir + "/" + saveName + ".png" , dpi = 300, bbox_inches='tight')
            plt.close(fig)

            

    def saveStatus( self ):
        '''
        その時点のModelの状態を保存
        '''
        StepperList = self.aSession.getStepperList() 
        for Stepper in StepperList:
            aStub = self.aSession.createStepperStub( Stepper )
            aStubDict = {}
            for key2 in aStub.getPropertyList( ):
                if aStub.getPropertyAttributes( key2 )[ 1 ] == 1:
                    aStubDict[ key2 ] = aStub.getProperty( key2 ) 
                else:
                    pass 

            self.saveStepperDict[ Stepper ] = aStubDict
            del aStub 

        for key in self.treeDictKeys:
            properties = self.treeDict[ key ]
            for j in range( 1,3 ):
                for path in properties[j]:
                    aEntity = self.aSession.createEntityStub( path )
                    propertyValueDict = {}
                    for k in aEntity.getPropertyList():
                        if aEntity.getPropertyAttributes( k )[ 1 ] == 1:
                            propertyValueDict[ k ] = aEntity.getProperty( k ) 
                        else: 
                            pass 

                    self.saveEntityDict[ path ] = propertyValueDict
                    del aEntity
        


    def resetStatus( self ):
        '''
        saveStatusで保存した時点のモデルの状態にリセット
        '''
        StepperList = self.aSession.getStepperList()
         
        for Stepper in StepperList:
            aStub = self.aSession.createStepperStub( Stepper )
            #print aStub[ 'StepInterval' ],
            #print self.saveStepperDict[ Stepper ][ 'StepInterval' ] i
            #if aStub[ 'ClassName' ] == 'ODE':
            #    aStub[ 'NextTime' ] = self.aSession.getCurrentTime() + self.saveStepperDict[ Stepper ][ 'StepInterval' ]

            #else:
            aStub[ 'StepInterval' ] = self.saveStepperDict[ Stepper ][ 'StepInterval' ]
            del aStub
                                   
        for key in self.treeDictKeys:
            properties = self.treeDict[ key ]
            for j in range(1,3):
                for path in properties[j]:
                    aEntity = self.aSession.createEntityStub( path )
                    propertyValueDict = self.saveEntityDict[ path ]
                    aEntity[ self.PropertyList[ j ] ] = propertyValueDict[ self.PropertyList[ j ] ]
                    del aEntity


    
if __name__ == '__builtin__':
    loadModel('./BIOMD0000000008.eml')
    EX = EX( self )
    print EX.getAllEntityList( '/' )
    EX.treeDictionary( '/' ) 
    print EX.treeDict
    print EX.treeDictKeys
    EX.saveStatus() 
    EX.createAllLogger()
    print 'save' 
    run( 100 )
    EX.resetStatus() 
    run( 100 )
    print 'reset'
    EX.saveAllCSV("AllData.csv", 0, 500, 0.01)
    EX.graphAll( "AllData.csv", "img") 
    print 'finish' 
    
        
