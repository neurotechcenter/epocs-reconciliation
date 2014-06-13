# -*- coding: utf-8 -*-
import md5, os, time, re, unicodedata
		
class MultiMatch:
	
	def ExpandPattern( self, expression, groupName=None ):
		for k, v in self.__dict__.items(): expression = expression.replace( '$%s' % k, '(%s)' % v )
		if groupName: expression = '(?P<%s>%s)' % ( groupName, expression )
		return expression
	def Add( self, expression, groupName, key=None ):
		if key == None: key = groupName
		self.__dict__[ key ] = self.ExpandPattern( expression, groupName )
	def __setattr__( self, key, value ):
		self.Add( value, key )
	def __getattr__( self, key ):
		if key in self.__dict__: return self.__dict__[ key ]
		else: raise AttributeError( "'%s' object has no attribute or item '%s'" % ( self.__class__.__name__, key ) )
	__setitem__ = __setattr__
	__getitem__ = __getattr__

	def Match( self, string, *expressions ):
		if len( expressions ) == 0: expressions = sorted( k for k in self.__dict__.keys() if isinstance( k, int ) )
		for expression in expressions:
			if expression in self.__dict__: expression = self.__dict__[ expression ]
			else: expression = self.ExpandPattern( expression )
			string = string.replace( '.', ' ' )
			while '  ' in string: string = string.replace( '  ', ' ' )
			string = string.strip()
			m = re.match( '^' + expression + '$', string, re.IGNORECASE )
			if m != None: return m.groupdict()
	
	def Test( self, string, *expressions, **kwargs ):
		if len( expressions ) == 0: expressions = sorted( k for k in self.__dict__.keys() if isinstance( k, int ) )
		showAll = kwargs.pop( 'showAll', False )
		if showAll: results = [ ( expression, self.Match( string, expression ) ) for expression in expressions ]
		else: results = [ ( '    '.join( str( x ) for x in expressions ), self.Match( string, *expressions ) ) ]
		for expression, result in results:
			print expression
			print repr( string )
			if result == None: print 'NO MATCH'
			else:
				for k, v in sorted( result.items() ): print '%20s : %s,' % ( k, repr( v ) )
		if showAll: print '*****\n'
		else: print
	
NameMatcher = MultiMatch()
NameMatcher.Add( ur'van der|van|von der|von und zu|von|zu|de la|del|de',       'AristocraticPrefix' )
NameMatcher.Add( ur'X|IX|VIII|VII|VI|V|IV|III|II|I|Junior|Jr\.?|Senior|Sr\.?', 'DynasticSuffix' )
NameMatcher.Add( ur'($AristocraticPrefix\s+)?[^,\s]+?', 'FamilyName', 'FamilyNameWithoutSpaces' )
NameMatcher.Add( ur'($AristocraticPrefix\s+)?[^,]+?',   'FamilyName', 'FamilyNameWithSpaces' )
NameMatcher.Add( ur'$AristocraticPrefix\s+[^,]+?',      'FamilyName', 'AristocraticFamilyNameWithSpaces' )
NameMatcher.Add( ur'\s*,\s*',     None, 'Comma' )
NameMatcher.Add( ur'\s*,\s*|\s+', None, 'PossibleComma' )
NameMatcher.Add( ur'[^,]+?', 'GivenNames' )
NameMatcher.Add( ur'$FamilyNameWithSpaces($PossibleComma$DynasticSuffix)?$Comma$GivenNames', None, 1 )
NameMatcher.Add( ur'$FamilyNameWithSpaces$Comma$GivenNames($PossibleComma$DynasticSuffix)?', None, 2 )
NameMatcher.Add( ur'$GivenNames\s+$AristocraticFamilyNameWithSpaces($PossibleComma$DynasticSuffix)?', None, 3 )
NameMatcher.Add( ur'$GivenNames\s+$FamilyNameWithoutSpaces($PossibleComma$DynasticSuffix)?', None, 4 )

class HumanName:
	def __init__( self, s ):
		self.fieldOrder = 'FamilyName GivenNames DynasticSuffix Year Month Day Serial'.split()
		if isinstance( s, basestring ):
			m = NameMatcher.Match( s )
			if m == None: raise ValueError( 'could not interpret "%s" as a name' % s )
			s = m
		for key in self.fieldOrder:
			self.__dict__[ key ] = s.get( key, '' )
	
	def Test( self ):
		print repr( self.Full )
		print repr( self.Unambiguous )
		print repr( self.Standardized )
		print 
		return self
		
	def Standardize( self, s ):
		if not isinstance( s, unicode ): s = s.decode( 'utf-8' )
		s = s.replace( '.', ' ' )
		while '  ' in s: s = s.replace( '  ', ' ' )
		s = unicodedata.normalize( 'NFD', s ).encode( 'ascii', 'ignore' )
		s = s.upper()
		return s
		
	def Get( self, key, standardized=False ):
		s = getattr( self, key )
		if s == None: s = ''
		if standardized: s = self.Standardize( s )
		return s
		
	@apply
	def Full():
		def fget( self ): return ' '.join( self.Get( key ) for key in 'GivenNames FamilyName DynasticSuffix'.split() if self.Get( key ) )
		return property( fget=fget )
	
	@apply
	def Unambiguous():
		def fget( self ): return ', '.join( self.Get( key ) for key in 'FamilyName GivenNames DynasticSuffix'.split() if self.Get( key ) )
		return property( fget=fget )
		
	@apply
	def Standardized():
		def fget( self ): return ', '.join( self.Get( key, standardized=True ) for key in 'FamilyName GivenNames DynasticSuffix'.split() if self.Get( key ) )
		return property( fget=fget )
	
	def Initials( self, given=True, family=False, long=False, max=None, spaces=True ):
		def _initials( s, delim ): return delim.join( x[ 0 ] for x in s.split( delim ) if len( x ) )
		names = []
		if given:  names += self.Get( 'GivenNames', standardized=True ).split()
		if family: names += self.Get( 'FamilyName', standardized=True ).split()
		if len( names ) == 1:
			longer  = _initials( names[ 0 ], '-' )
			shorter = _initials( names[ 0 ], ' ' )
		else:
			names = ' '.join( names )
			longer  = _initials( names.replace( '-', ' ' ), ' ' )
			shorter = _initials( names, ' ' )
		if long: out = longer
		else: out = shorter
		if max != None: out = ' '.join( out.split()[ : max ] )
		if not spaces: out = out.replace( ' ', '' )
		return out
		
	def Similarity( self, other ):
		if isinstance( other, basestring ):
			try: string, other = other, HumanName( other )
			except: string, other = other, None
		
		sFN =  self.Get( 'FamilyName', standardized=True )
		
		string = self.Standardize( string )
		if string == sFN: return 0.5
		if string == sFN.split()[ 0 ]: return 0.25
		if string == self.Initials( given=True, family=False, long=True  ) + ' ' + sFN: return 0.9
		if string == self.Initials( given=True, family=False, long=False ) + ' ' + sFN: return 0.8
		if string == self.Initials( given=True, family=False, long=True , spaces=False ) + ' ' + sFN: return 0.7
		if string == self.Initials( given=True, family=False, long=False, spaces=False ) + ' ' + sFN: return 0.6
		if string == self.Initials( given=True, family=False, long=True,  max=1 ) + ' ' + sFN: return 0.7
		if string == self.Initials( given=True, family=False, long=False, max=1 ) + ' ' + sFN: return 0.6
		if string == self.Initials( given=True, family=True, long=True  ): return 0.6
		if string == self.Initials( given=True, family=True, long=False ): return 0.5
		if string == self.Initials( given=True, family=True, long=True , spaces=False ): return 0.4
		if string == self.Initials( given=True, family=True, long=False, spaces=False ): return 0.3
		if string == self.Initials( given=True, family=False, long=True,  max=1 ) + ' ' + self.Initials( given=False, family=True, long=True,  max=1 ): return 0.1
		if string.replace( ' ', '' ) == self.Initials( given=True, family=True, long=True , spaces=False ): return 0.2
		if string.replace( ' ', '' ) == self.Initials( given=True, family=True, long=False, spaces=False ): return 0.1
		if string.replace( ' ', '' ) == self.Initials( given=True, family=False, long=True,  max=1, spaces=False ) + self.Initials( given=False, family=True, long=True,  max=1, spaces=False ): return 0.1
		if string.replace( ' ', '' ) == self.Initials( given=True, family=False, long=False, max=1, spaces=False ) + self.Initials( given=False, family=True, long=False, max=1, spaces=False ): return 0.1
		if string == None: return 0.0
			
		similarity = 1.0
		oFN = other.Get( 'FamilyName', standardized=True )
		if sFN == oFN: pass
		elif sFN == other.Initials( given=False, family=True, long=True  ): similarity *= 0.6
		elif oFN ==  self.Initials( given=False, family=True, long=True  ): similarity *= 0.6
		elif sFN == other.Initials( given=False, family=True, long=False ): similarity *= 0.5
		elif oFN ==  self.Initials( given=False, family=True, long=False ): similarity *= 0.5
		elif sFN == other.Initials( given=False, family=True, long=True  ).replace( ' ', '' ): similarity *= 0.4
		elif oFN ==  self.Initials( given=False, family=True, long=True  ).replace( ' ', '' ): similarity *= 0.4
		elif sFN == other.Initials( given=False, family=True, long=False ).replace( ' ', '' ): similarity *= 0.3
		elif oFN ==  self.Initials( given=False, family=True, long=False ).replace( ' ', '' ): similarity *= 0.3
		elif sFN == other.Initials( given=False, family=True, long=True,  max=1 ): similarity *= 0.2
		elif oFN ==  self.Initials( given=False, family=True, long=True,  max=1 ): similarity *= 0.2
		elif sFN == other.Initials( given=False, family=True, long=False, max=1 ): similarity *= 0.1
		elif oFN ==  self.Initials( given=False, family=True, long=False, max=1 ): similarity *= 0.1
		else: return 0.0
		
		sGN =  self.Get( 'GivenNames', standardized=True )
		oGN = other.Get( 'GivenNames', standardized=True )
		if sGN == oGN: pass
		elif sGN == other.Initials( given=True, family=False, long=True  ): similarity *= 0.9
		elif oGN ==  self.Initials( given=True, family=False, long=True  ): similarity *= 0.9
		elif sGN == other.Initials( given=True, family=False, long=False ): similarity *= 0.8
		elif oGN ==  self.Initials( given=True, family=False, long=False ): similarity *= 0.8
		elif sGN == other.Initials( given=True, family=False, long=True  ).replace( ' ', '' ): similarity *= 0.7
		elif oGN ==  self.Initials( given=True, family=False, long=True  ).replace( ' ', '' ): similarity *= 0.7
		elif sGN == other.Initials( given=True, family=False, long=False ).replace( ' ', '' ): similarity *= 0.6
		elif oGN ==  self.Initials( given=True, family=False, long=False ).replace( ' ', '' ): similarity *= 0.6
		elif sGN == other.Initials( given=True, family=False, long=True,  max=1 ): similarity *= 0.5
		elif oGN ==  self.Initials( given=True, family=False, long=True,  max=1 ): similarity *= 0.5
		elif sGN == other.Initials( given=True, family=False, long=False, max=1 ): similarity *= 0.4
		elif oGN ==  self.Initials( given=True, family=False, long=False, max=1 ): similarity *= 0.4
		elif oGN == '' or sGN == '': similarity *= 0.3
		else: return 0.0
		
		sDS =  self.Get( 'DynasticSuffix', standardized=True )
		oDS = other.Get( 'DynasticSuffix', standardized=True )
		if sDS == oDS: pass
		elif sDS == '' or oDS == '': similarity *= 0.75
		else: return 0.0
		
		return similarity
		
	
class Anonymizer:
	def __init__( self ):
		self.fileName = 'subjectdb.txt'
		self.fieldOrder = 'FamilyName GivenNames Year Month Day Serial'
		if not os.path.isfile( self.fileName ): open( self.fileName, 'wt' ).write( '{}\n' )
		self.Read()
		print repr( self.db )
	
	
	def Read( self ):
		db = eval( open( self.fileName, 'rt' ).read() )
		self.db = {}
		for k, v in db.items(): self.db[ k ] = self.DecodeEntry( v )
		
	def Write( self ):
		fh = open( self.fileName, 'wt' )
		flat = sorted( [ ( self.EncodeEntry( v ), k ) for k, v in self.db.items() ] )
		fh.write( '{\n' )
		for v, k in flat: fh.write( '   %s : %s,\n' % ( repr( k ), v ) )
		fh.write( '}\n' )
		fh.close()
	
	def EncodeEntry( self, record ):
		out = ''
		out += '{'
		for key in self.fieldOrder.split():
			value = record.get( key, '' )
			if key in [ 'Year' ]:
				if isinstance( value, basestring ): value = int( value )
				if len( str( value ) ) < 4:
					year = time.localtime().tm_year
					century = 100 * ( int( year / 100 ) )
					value = century + value
					if value > year: value -= 100
				value = '%04d' % value
			elif key in [ 'Month', 'Day' ]:
				if isinstance( value, basestring ): value = int( value )
				value = '%02d' % value
			elif key in [ 'GivenNames' ]:
				value = u' '.join( v.strip() for v in value if v not in ' .-' )
			value = unicode( value ).encode( 'UTF-8' )
			value = value.strip( ' .' )
			while '  ' in value: value = value.replace( '  ', ' ' )
			out += ' %s : %s,' % ( repr( key ), repr( value ) )
		out += ' }'
		return out
	
	def DecodeEntry( self, record ):
		out = {}
		if isinstance( record, basestring ) and len( record.strip() ) == 0: record = {}
		if isinstance( record, basestring ): record = eval( record )
		for key in self.fieldOrder.split():
			value = record.get( key, '' )
			if not isinstance( value, basestring ): value = unicode( value )
			if not isinstance( value, unicode ): value = value.decode( 'UTF-8' )
			if key in [ 'Year', 'Month', 'Day' ] and len( value ): value = int( value )
			out[ key ] = value
		return out
	
	def HashEntry( self, record ):
		h = md5.md5()
		h.update( self.EncodeEntry( record ).upper() )
		return h.hexdigest().upper()[ : 5 ]
	
	def Add( self, record=None, **kwargs ):
		if record == None: record = {}
		blank = self.DecodeEntry( {} )
		if isinstance( record, basestring ): record = eval( record )
		record.update( kwargs )
		for k, v, in record.items():
			if k not in blank: raise KeyError( 'unrecognized field %s' % repr( k ) )
		record = self.DecodeEntry( record )
		for k in self.fieldOrder.split():
			if record[ k ] in [ '', None ] and k not in [ 'MiddleInitials', 'Serial' ]: raise ValueError( '%s field is empty' % repr( k ) )
		# TODO: serial
		key = self.HashEntry( record )
		self.db[ key ] = record
		return key
	
	def Similar( self, r1, r2 ):
		r1 = self.DecodeEntry( self.EncodeEntry( r1 ) )
		r2 = self.DecodeEntry( self.EncodeEntry( r2 ) )
		
if __name__ == '__main__':
	HumanName( 'Charles-Jean Étienne Gustave Nicolas de la Vallée Poussin IX' ).Test()
	HumanName( 'Robert Downey Jr.' ).Test()
	HumanName( 'Robert John Downey Jr.' ).Test()
	HumanName( 'Downey Jr, Robert' ).Test()
	HumanName( 'Downey Jr, Robert John' ).Test()
	HumanName( 'Downey, Robert, Jr' ).Test()
	HumanName( 'Downey, Robert John, Jr' ).Test()
	HumanName( 'Quiñonero Candela, Joaquin' ).Test()
	
	